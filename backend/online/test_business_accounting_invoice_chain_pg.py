"""Production issuer, runtime PostgreSQL/MFA/HTTP and actual chain restore."""
from concurrent.futures import ThreadPoolExecutor
import json
import unittest

import business_schema
from business_accounting_components import DocumentComponents
from business_accounting_capacity import ReusableDocumentComponents
from business_accounting_refunds import RefundOrigins
from business_accounting_refunds_v2 import VersionedRefundOrigins
from business_accounting_euer import EuerAccounting
from core import Problem
from online import test_business_accounting_euer_pg as fixture
from online import release
from online.store import PostgresOffice, migrate
from online.test_postgres_accounting_components_integration import disposable_restore, evidence_for, approve

req = fixture.req


@unittest.skipUnless(fixture.fixture.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class InvoiceChainPostgres(unittest.TestCase):
    for _name,_value in vars(fixture.EuerPostgres).items():
        if not _name.startswith('_') and not _name.startswith('test_'):
            locals()[_name]=_value

    def cash_event(self, invoice, amount, kind='receipt'):
        payment = self.payment(invoice,amount,kind=kind)
        source = next(value for value in self.call('GET','/business/accounting/sources/payments').json['items'] if value['payment_id']==payment['id'])
        return self.call('POST','/business/accounting/events/import-payment',req(confirmation=True,payment_id=payment['id'],source_hash=source['source_hash'],
            account_id=self.account['id'],account_revision=1,cash_date=self.today,evidence_reference='Synthetic bank '+payment['id']),status=201).json

    def component_command(self,event,current=False):
        path='/business/accounting/components/'+('v2/' if current else '')+'events/'+event['id']
        state=self.call('GET',path).json; portion=self.call('GET',path+'/portions').json['items'][0]
        body=dict(source_hash=state['source_hash'],expected_revision=state['revision'],state_hash=state['state_hash'],
            portion_id=portion['portion_id'],portion_state_hash=portion['portion_state_hash'],
            groups=[dict(group_id=portion['groups'][0]['group_id'],amount=portion['amount'])],reason='Exact incremental contract source')
        if current:body['action']=portion['action']
        preview=self.call('POST',path+'/preview',body).json
        return path,req(**body,confirmation=True,preview_hash=preview['preview_hash'])

    def component(self,event,current=False):
        path,command=self.component_command(event,current)
        value=self.call('POST',path+'/confirm',command,status=201).json
        self.receipts.append((path+'/confirm',command,value))
        return value

    def returned(self,event,selected,current=False):
        path='/business/accounting/refunds/'+('v2/' if current else '')+'events/'+event['id']
        state=self.call('GET',path).json; portion=self.call('GET',path+'/portions').json['items'][0]
        candidates=self.call('GET',path+'/origins?portion_id='+portion['portion_id']).json['items']; origins=[]
        for version,entry,amount in selected:
            group=entry['lines'][0]['group_id']
            candidate=next(value for value in candidates if value['entry_id']==entry['id'] and value['group_id']==group
                and (not current or value['origin_version']==version))
            origin=dict(entry_id=entry['id'],group_id=group,lot_state_hash=candidate['lot_state_hash'],amount=amount)
            if current:origin['origin_version']=version
            origins.append(origin)
        body=dict(source_hash=state['source_hash'],expected_revision=state['revision'],state_hash=state['state_hash'],
            portion_id=portion['portion_id'],portion_state_hash=portion['portion_state_hash'],origins=origins,reason='Explicit incremental refund origin')
        if current:body['action']=portion['action']
        preview=self.call('POST',path+'/preview',body).json; command=req(**body,confirmation=True,preview_hash=preview['preview_hash'])
        value=self.call('POST',path+'/confirm',command,status=201).json
        self.receipts.append((path+'/confirm',command,value)); return value

    def seed(self):
        self.assertTrue(business_schema.require_runtime_security(self.office)); self.profile(); self.issuer(); self.receipts=[]
        self.account=self.call('POST','/business/accounting/accounts',req(confirmation=True,code='BANK',name='Synthetic chain bank',kind='bank'),status=201).json
        project=self.project()
        first=self.invoice(project,'30.00',kind='advance_invoice')
        middle=self.invoice(project,'70.00',kind='cumulative_invoice',previous=[first['id']])
        last=self.invoice(project,'100.00',kind='final_invoice',previous=[middle['id']])
        return first,middle,last

    def test_real_chain_refund_reuse_euer_migration_restart_and_dump_restore(self):
        first,middle,last=self.seed()
        normal=self.invoice(self.project(),'100.00'); self.component(self.cash_event(normal,'119.00'))
        normal_receipt=self.receipts[-1]
        normal_id=normal_receipt[2]['id']
        original=dict(self.office.db.execute('SELECT * FROM business_accounting_component_entries WHERE id=?',(normal_id,)).fetchone())
        proof=json.loads(original['proof_json']); self.assertEqual(proof['archive']['kind'],'document')
        self.assertNotIn('invoice_chain',proof['archive'])
        self.component(self.cash_event(first,'35.70')); self.component(self.cash_event(middle,'47.60'))
        origin=self.component(self.cash_event(last,'35.70'))
        self.returned(self.cash_event(last,'11.90','refund'),[('c1',origin,'11.90')])
        reused=self.component(self.cash_event(last,'11.90'),True)
        returned=self.returned(self.cash_event(last,'23.80','refund'),[('c1',origin,'11.90'),('c2',reused,'11.90')],True)
        self.assertEqual((returned['net'],returned['tax']),('20.00','3.80'))
        self.component(self.cash_event(last,'23.80'),True)
        self.assertEqual(dict(self.office.db.execute('SELECT * FROM business_accounting_component_entries WHERE id=?',(normal_id,)).fetchone()),original)
        self.assertEqual(self.call('POST',normal_receipt[0],normal_receipt[1],status=201).json,normal_receipt[2])
        for row in self.office.db.execute('SELECT id FROM business_accounting_cash_events ORDER BY sequence').fetchall():
            event=self.call('GET','/business/accounting/events/'+row['id']).json
            entry,command=self.post('cash',self.cash(event));self.receipts.append(('/business/accounting/euer/confirm',command,entry))
        report=self.call('GET','/business/accounting/euer/report?year='+self.today[:4]).json
        self.assertTrue(report['complete_for_recorded_sources'],report['issues'])
        self.assertEqual((report['totals']['confirmed_income'],report['totals']['confirmed_output_vat']),('238.00','38.00'))
        exported,command=self.post('export',{'year':int(self.today[:4])})
        frozen=self.call('GET','/business/accounting/euer/exports/'+exported['id']).json
        self.reopen()
        for path,body,expected in self.receipts:self.assertEqual(self.call('POST',path,body,status=201).json,expected)
        # This adds a versioned JSON proof only; migration must leave all data,
        # module checksums and ordinary C1/R1/C2/R2 archives untouched.
        before=release.snapshot_fingerprint(fixture.fixture.DSN)
        self.office.db.close()
        migrate(fixture.fixture.DSN,owner_role='smartplan-migrator',compatibility_mode='business',require_business_modules=True)
        self.assertEqual(release.snapshot_fingerprint(fixture.fixture.DSN),before)
        release.secure_database(fixture.fixture.DSN,test_mode=True);self.reopen()
        owner=dict(self.office.db.execute("SELECT * FROM users WHERE email='order-owner@example.test'").fetchone())
        horizon=business_schema.financial_accounting_horizon(self.office);self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,restore_report):
            office=PostgresOffice(runtime)
            try:
                self.assertEqual(business_schema.financial_accounting_horizon(office),horizon)
                self.assertEqual(EuerAccounting(office).exported(owner,exported['id']),frozen)
                with self.assertRaises(Problem):EuerAccounting(office).confirm(owner,command)
            finally:office.db.close()
            operator=PostgresOffice(target)
            try:approve(operator,evidence_for(operator,restore_report))
            finally:operator.db.close()
            office=PostgresOffice(runtime)
            try:
                self.assertEqual(EuerAccounting(office).confirm(owner,command),exported)
                for path,body,expected in self.receipts:
                    if '/euer/' in path:value=EuerAccounting(office).confirm(owner,body)
                    else:
                        api=(VersionedRefundOrigins if '/refunds/v2/' in path else RefundOrigins if '/refunds/' in path
                             else ReusableDocumentComponents if '/components/v2/' in path else DocumentComponents)(office)
                        value=api.confirm(owner,path.split('/')[-2],body)
                    self.assertEqual(value,expected)
                self.assertTrue(business_schema.validate_integrity(office))
            finally:office.db.close()

    def test_independent_connections_compete_once_and_revoked_reader_cannot_replay(self):
        first,middle,last=self.seed();event=self.cash_event(last,'35.70')
        path,command=self.component_command(event)
        owner=dict(self.office.db.execute("SELECT * FROM users WHERE email='order-owner@example.test'").fetchone())
        def run(unused):
            office=PostgresOffice(self.runtime)
            try:return DocumentComponents(office).confirm(owner,event['id'],command)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(run,range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_accounting_component_entries').fetchone()[0],1)
        self.office.add_user('chain-reader@example.test','Synthetic-chain-password-123','technician')
        token=self.login('chain-reader@example.test','Synthetic-chain-password-123')
        denied=self.call('POST',path+'/confirm',command,token=token,status=403).json
        self.assertNotIn('request_resolution',denied)
        self.assertEqual(self.call('POST',path+'/confirm',command,status=201).json,results[0])


if __name__=='__main__':unittest.main()
