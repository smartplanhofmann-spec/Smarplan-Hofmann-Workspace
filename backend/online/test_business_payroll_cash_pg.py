"""Bound real PostgreSQL cash sources, prior schema9 and actual dump/restore."""
from concurrent.futures import ThreadPoolExecutor
import json
import unittest
from unittest.mock import patch

import psycopg
import business_schema
from business_accounting_euer import EuerAccounting
from business_payroll_cash import PayrollCash,TABLES,validate_integrity
from payroll_cash_sources import calculated
from online import release,test_business_company_handover_pg as bound,test_business_payroll_pg as payroll
from online.store import PostgresOffice,migrate
from online.test_postgres_accounting_components_integration import disposable_restore,evidence_for,approve
import test_business_payroll_cash as domain
import test_business_payroll_accounts as account_fixture

fixture=bound.fixture.fixture
req=bound.req


@unittest.skipUnless(fixture.DSN,'Disposable loopback SMARTPLAN_TEST_DSN required')
class PayrollCashPostgres(unittest.TestCase):
    setUp=bound.CompanyHandoverPostgres.setUp
    reopen=bound.CompanyHandoverPostgres.reopen
    login=bound.CompanyHandoverPostgres.login
    call=bound.CompanyHandoverPostgres.call
    profile=bound.fixture.EuerPostgres.profile
    post=bound.fixture.EuerPostgres.post
    body=domain.PayrollCashTests.body
    payload=domain.PayrollCashTests.payload

    def workflow(self):
        data=payroll.RegularPayrollPostgres.workflow(self);employee=data['hr']['employee'];original=data['hr']['file']
        details=account_fixture.PayrollAccountTests.identity_details(self,data,employment_from=self.today[:7]+'-01',employment_to='2026-11-30',valid_from=data['profile']['profile']['effective_from'])
        identity=self.call('POST','/business/payroll/account-records',req(employee_id=employee['id'],kind='identity',revision=0,source_file_id=original['id'],confirmed=True,details=details)).json
        paid=self.call('POST','/business/payroll/account-records',req(employee_id=employee['id'],kind='payment',revision=0,source_file_id=original['id'],confirmed=True,
            details=dict(run_id=data['run']['id'],run_revision=1,identity_id=identity['id'],identity_revision=1,
                payments=[dict(paid_on=self.today,amount_minor=313009,payment_reference='SYN-PG-ACTUAL-NET')],tax_free_payments_minor=0,tax_free_basis='',standard_case_confirmed=True))).json
        self.account=self.call('POST','/business/accounting/accounts',req(confirmation=True,code='PAYROLL',name='Synthetic payroll company bank',kind='bank'),status=201).json
        self.profile()
        return data,paid

    def command(self,body):
        preview=self.call('POST','/business/payroll/cash/preview',body).json
        return req(**body,preview_hash=preview['preview_hash'],confirmation=True)

    def remittance(self,data,paid):
        run=data['run'];original=data['hr']['file'];amounts=calculated(run['calculation'])
        return self.body(paid,kind='remittance',sources=[dict(source_kind='run',id=run['id'],revision=1,content_hash=run['content_hash'],amounts=amounts)],
            settlement=dict(paid_on=self.today,payment_reference='SYN-PG-ACTUAL-SV-TAX',amount_minor=sum(amounts.values()),source_file_id=original['id'],employee_id=data['hr']['employee']['id'],sha256=original['sha256']))

    def test_actual_http_net_and_remittances_runtime_acl_restart_and_real_restore(self):
        data,paid=self.workflow();command=self.command(self.body(paid))
        saved=self.call('POST','/business/payroll/cash/batches',command,status=201).json;self.post('payroll_cash',self.payload(saved))
        remit=self.call('POST','/business/payroll/cash/batches',self.command(self.remittance(data,paid)),status=201).json;self.post('payroll_cash',self.payload(remit))
        report=self.call('GET','/business/accounting/euer/report?year=2026').json
        self.assertEqual(report['totals']['confirmed_expenses'],'6192.00');self.assertEqual(report['totals']['confirmed_input_vat'],'0.00')
        export,_=self.post('export',dict(year=2026));frozen=self.call('GET','/business/accounting/euer/exports/'+export['id']).json
        for secret in (data['hr']['employee']['id'],paid['id'],data['hr']['file']['id'],'SYN-PG-ACTUAL-NET','12345678903'):
            self.assertNotIn(secret,json.dumps(frozen))
        self.call('GET','/business/payroll/cash',token=data['hr']['token'],status=403)
        for table in TABLES:
            with self.subTest(table=table),self.assertRaises(psycopg.errors.InsufficientPrivilege):
                with self.office.db:self.office.db.execute('DELETE FROM '+table)
        self.reopen();self.assertEqual(self.call('POST','/business/payroll/cash/batches',command,status=201).json,saved)
        before=release.snapshot_fingerprint(fixture.DSN);self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,restored_report):
            restored=PostgresOffice(runtime)
            try:
                self.assertEqual(EuerAccounting(restored).exported(self.owner,export['id']),frozen)
                self.assertTrue(validate_integrity(restored))
                with self.assertRaises(Exception):PayrollCash(restored).confirm(self.owner,command)
            finally:restored.db.close()
            operator=PostgresOffice(target)
            try:
                evidence=evidence_for(operator,restored_report);self.assertEqual(evidence['schema'],12)
                self.assertEqual(evidence['accounting_horizon']['payroll_cash']['table_counts']['business_payroll_cash_batches'],2)
                approve(operator,evidence)
            finally:operator.db.close()
            restored=PostgresOffice(runtime)
            try:
                self.assertEqual(PayrollCash(restored).confirm(self.owner,command),saved)
                self.assertEqual(EuerAccounting(restored).report(self.owner,2026)['totals']['confirmed_expenses'],'6192.00')
                business_schema.validate_integrity(restored)
            finally:restored.db.close()
            after=release.snapshot_fingerprint(target)
            for table in TABLES:self.assertEqual(before[table],after[table])

    def test_separate_connections_same_nonce_create_one_actual_cash_batch(self):
        data,paid=self.workflow();command=self.command(self.body(paid))
        def apply(_):
            office=PostgresOffice(self.runtime)
            try:return PayrollCash(office).confirm(self.owner,command)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(apply,range(2)))
        self.assertEqual(results[0],results[1]);self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_payroll_cash_batches').fetchone()[0],1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_payroll_cash_parts').fetchone()[0],1)
        self.assertTrue(validate_integrity(self.office))

    def test_additive_migration_keeps_confirmed_schema9_receipt_and_requires11_for_new_restore(self):
        self.office.db.close();full=business_schema.registry();prior=tuple(spec for spec in full if spec.name not in ('business_payroll_cash','business_bank_reconciliation', 'business_travel_allowances'))
        with patch.object(business_schema,'registry',return_value=prior),patch.object(business_schema,'MODULE_NAMES',tuple(spec.name for spec in prior)):
            self.setUp();data,paid=self.workflow();old_export,_=self.post('export',dict(year=2026))
            original=self.call('GET','/business/accounting/euer/exports/'+old_export['id']).json
            before=release.snapshot_fingerprint(fixture.DSN);self.office.db.close()
            with disposable_restore(self.runtime) as (target,runtime,report):
                operator=PostgresOffice(target)
                try:evidence=evidence_for(operator,report);self.assertEqual(evidence['schema'],9);accepted=approve(operator,evidence)
                finally:operator.db.close()
                old_target=release.snapshot_fingerprint(target)
                with patch.object(business_schema,'registry',return_value=full),patch.object(business_schema,'MODULE_NAMES',tuple(spec.name for spec in full)):
                    migrate(target,owner_role='smartplan-migrator',compatibility_mode='business',require_business_modules=True)
                    changed=release.snapshot_fingerprint(target)
                    for table,value in old_target.items():
                        if table not in ('business_schema_migrations','business_schema_state','business_schema_events'):self.assertEqual(changed[table],value,table)
                    operator=PostgresOffice(target)
                    try:
                        self.assertEqual(business_schema.financial_accounting_horizon(operator)['schema_version'],11)
                        self.assertEqual(approve(operator,evidence),accepted)
                        self.assertEqual(EuerAccounting(operator).exported(self.owner,old_export['id']),original)
                    finally:operator.db.close()
        migrate(fixture.DSN,owner_role='smartplan-migrator',compatibility_mode='business',require_business_modules=True)
        after=release.snapshot_fingerprint(fixture.DSN)
        for table,value in before.items():
            if table not in ('business_schema_migrations','business_schema_state','business_schema_events'):self.assertEqual(after[table],value,table)
        release.secure_database(fixture.DSN,test_mode=True);self.reopen()
        self.call('POST','/business/payroll/cash/batches',self.command(self.body(paid)),status=201);self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,report):
            operator=PostgresOffice(target)
            try:
                with self.assertRaises(Exception):approve(operator,dict(evidence,restore_id=report['restore_id']))
                new=evidence_for(operator,report);self.assertEqual(new['schema'],12);approve(operator,new)
            finally:operator.db.close()


if __name__=='__main__':unittest.main()
