"""Registered Source5 actual MFA/PostgreSQL claims, payments and backup restore."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import tempfile
import threading
import unittest

import psycopg
from psycopg.conninfo import make_conninfo
import business_api
import business_schema
from business_payroll import Payroll
from business_payroll_accounts import PayrollAccounts
from business_payroll_annual_basis import PayrollAnnualBasis
from business_payroll_facts import reference
from business_payroll_multiple_cases import PayrollMultipleCases,RULE_VERSION,TABLES,_consumption_row
from core import Problem
from online import release,test_business_payroll_oneoff_pg as original_pg
from online.backup import backup
from online.restore import restore,complete_restore
from online.store import PostgresOffice

fixture=original_pg.fixture
journey=original_pg.journey
req=original_pg.req


@unittest.skipUnless(fixture.DSN,'Guarded disposable loopback PostgreSQL fixture required')
class MultiplePayrollPostgres(unittest.TestCase):
    reopen=journey.CustomerExecutionJourneyPostgres.reopen
    login=journey.CustomerExecutionJourneyPostgres.login
    call=journey.CustomerExecutionJourneyPostgres.call
    sources=original_pg.OneoffPayrollPostgres.sources

    def setUp(self):
        self.assertEqual(business_schema.MODULE_NAMES.count('business_payroll_multiple_cases'),1)
        self.assertEqual(business_api.MODULES.count('business_payroll_multiple_cases'),1)
        journey.CustomerExecutionJourneyPostgres.setUp(self)
        self.owner=self.office.user(self.token)

    def workflow(self,*,save_case=True):
        data=original_pg.OneoffPayrollPostgres.workflow(self,save_case=False)
        old=data['oneoff_command'];details=old['details'];event=req()['request_id']
        original=dict(id=data['file']['id'],revision=1,content_hash=data['file']['content_hash'])
        proposal={key:old[key] for key in ('employee_id','employee_revision','source_file_ids')}
        proposal.update(kind='multiple_one_off_case',rule_version=RULE_VERSION,source_contract_version=1,
            details=dict(month=details['month'],running_calculation_case_ref=details['running_calculation_case_ref'],
                components=[dict(component_key=data['earning']['id'],earning_ref=reference(data['earning']),planned_receipts=[
                    dict(event_key=event,receipt_date='2026-10-31',gross_minor=50000,document_refs=[original])])],
                current_annual_basis_ref=details['current_annual_basis_ref'],previous_annual_basis_ref=None,
                annual_tax_forecasts=[dict(event_key=event,annual_tax_forecast_ref=details['annual_tax_forecast_ref'])],
                completeness=dict(month_events_complete=True,evidence_ref=original),verification_note='Actual PG monthly single original inspected'))
        preview=self.call('POST','/business/payroll/multiple-one-off-cases/preview',proposal).json
        self.assertTrue(preview['can_calculate'])
        command=req(**proposal,revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        data.update(multiple_command=command,event_key=event)
        if save_case:
            case=self.call('POST','/business/payroll/multiple-one-off-cases',command).json
            inputs=dict(employee_id=data['employee']['id'],source_schema_version=5,multiple_one_off_case_ref=reference(case))
            preview=self.call('POST','/business/payroll/preview',inputs).json
            data.update(multiple_case=case,run_command=req(**inputs,revision=0,confirmed=True,
                preview_hash=preview['preview_hash'],accepted_scope=preview['calculation']['scope']))
        return data

    def test_two_actual_finalize_writers_one_atomic_claim_event_and_private_rights(self):
        data=self.workflow();barrier=threading.Barrier(2)
        def writer(_):
            office=PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=10);return Payroll(office).finalize(self.owner,data['run_command'])
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:runs=list(pool.map(writer,range(2)))
        self.assertEqual(runs[0],runs[1]);run=runs[0]
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM '+TABLES[2]).fetchone()[0],1)
        proof=_consumption_row(self.office,run)
        self.assertEqual(proof['component_key'],data['earning']['id']);self.assertEqual(proof['event_key'],data['event_key'])
        path='/business/payroll/multiple-one-off-cases/'+data['multiple_case']['id']
        self.call('GET',path,token=data['tech'],status=403)
        offline=self.call('POST','/business/offline/access',{},status=201).json['token']
        self.call('GET',path,token=offline,status=403)
        self.call('POST','/business/payroll/multiple-one-off-cases?ignored=1',data['multiple_command'],status=400)
        self.call('GET',path,{},status=400)
        self.call('DELETE','/business/payroll/multiple-one-off-cases',{},status=405)
        for table in TABLES:
            column='id' if table.endswith('events') else 'request_id' if table.endswith('requests') else 'run_id'
            for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table,'TRUNCATE '+table):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:self.office.db.execute(statement)
            with psycopg.connect(fixture.DSN,autocommit=True) as operator:
                for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table):
                    with self.assertRaisesRegex(psycopg.Error,'immutable payroll multiple'):
                        with operator.transaction():
                            operator.execute('SET LOCAL ROLE "smartplan-migrator"');operator.execute(statement)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_distinct_actual_first_commands_cannot_create_two_month_owners(self):
        data=self.workflow(save_case=False);barrier=threading.Barrier(2)
        def writer(_):
            office=PostgresOffice(self.runtime);command=data['multiple_command']|req()
            try:
                barrier.wait(timeout=10)
                try:return ('accepted',PayrollMultipleCases(office).save(self.owner,command))
                except Problem as error:return ('rejected',error.status)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:values=list(pool.map(writer,range(2)))
        self.assertEqual(sorted(item[0] for item in values),['accepted','rejected'])
        self.assertEqual(next(item[1] for item in values if item[0]=='rejected'),409)
        for table in TABLES[:2]:self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],1)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_paid_v5_separate_day_source5_and_compact_annual_originals_restore_exactly(self):
        data=self.workflow();old=self.call('POST','/business/payroll/runs',data['command']).json
        actual=old['calculation']['net_minor']-old['calculation']['net_deductions_minor']
        parts=[dict(paid_on='2026-10-30',amount_minor=actual,payment_reference='SYN-PG-ACTUAL-RUNNING-30')]
        make_details=original_pg.running_pg.entitlement_pg.accounts.PayrollAccountTests.payment_details
        old_payment_command=req(employee_id=data['employee']['id'],kind='payment',revision=0,
            source_file_id=data['file']['id'],confirmed=True,details=make_details(self,old,data['identity'],payments=parts))
        old_payment=self.call('POST','/business/payroll/account-records',old_payment_command).json
        data['run_command'].update(id=old['id'],revision=1,correction_reason='One actual full bonus after earlier running transfer')
        run=self.call('POST','/business/payroll/runs',data['run_command']).json
        bonus=run['calculation']['net_minor']-run['calculation']['net_deductions_minor']-actual
        parts=parts+[dict(paid_on='2026-10-31',amount_minor=bonus,payment_reference='SYN-PG-ACTUAL-BONUS-31')]
        details=make_details(self,run,data['identity'],payments=parts)
        details.update(payment_source_schema_version=1,prior_payment_ref=reference(old_payment),settlement_allocations=[
            dict(payment_index=0,running_minor=actual,one_off_allocations=[]),
            dict(payment_index=1,running_minor=0,one_off_allocations=[dict(event_key=data['event_key'],net_minor=bonus)])])
        payment_command=req(employee_id=data['employee']['id'],kind='payment',revision=0,
            source_file_id=data['file']['id'],confirmed=True,details=details)
        payment=self.call('POST','/business/payroll/account-records',payment_command).json
        self.assertEqual(payment['sources']['single_payment_plan']['preserved_prior_payment_indexes'],[0])
        self.assertEqual(payment['sources']['single_payment_plan']['new_payment_indexes'],[1])
        details=deepcopy(data['annual_basis']['details']);details.update(as_of_date='2026-11-01',current_calculation_case_ref=None,
            payroll_run_refs=[reference(run)],payroll_payment_refs=[reference(payment)])
        proposal=dict(employee_id=data['employee']['id'],employee_revision=data['employee']['revision'],kind='annual_basis',
            details=details,source_file_ids=[data['file']['id']])
        preview=self.call('POST','/business/payroll/annual-facts/preview',proposal).json
        annual_command=req(**proposal,revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        annual=self.call('POST','/business/payroll/annual-facts',annual_command).json
        self.assertEqual(annual['plan']['earlier_other_taxable_minor'],50000)
        self.assertEqual(annual['sources']['payroll_runs'][0]['projection_format'],'source5_annual_reference_v1')
        proof=_consumption_row(self.office,run)
        pdf=Payroll(self.office).export(self.owner,run['id'],'pdf')[0]
        old_pdf=Payroll(self.office).export(self.owner,old['id'],'pdf',revision='1')[0]
        self.assertTrue(business_schema.validate_integrity(self.office))
        self.office.db.close();target=make_conninfo(fixture.DSN,dbname='smartplan_release_check')
        release.validate_dsns(fixture.DSN,target,test_mode=True)
        with psycopg.connect(fixture.DSN,autocommit=True) as operator:
            if operator.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():
                raise RuntimeError('Existing restore target must remain untouched')
            operator.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='synthetic-payroll-source5-backup-') as directory:
                archive=backup(fixture.DSN,directory)
                self.assertTrue(restore(archive,fixture.DSN,target,privileged_operator=True,test_mode=True)['restore_pending'])
            runtime=make_conninfo(self.runtime,dbname='smartplan_release_check')
            verifier=PostgresOffice(runtime,allow_restore_pending=True)
            try:self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally:verifier.db.close()
            restored=PostgresOffice(runtime)
            try:
                payroll=Payroll(restored);accounts=PayrollAccounts(restored)
                self.assertEqual(payroll.finalize(self.owner,data['command']),old)
                self.assertEqual(payroll.finalize(self.owner,data['run_command']),run)
                self.assertEqual(PayrollMultipleCases(restored).save(self.owner,data['multiple_command']),data['multiple_case'])
                self.assertEqual(accounts.save(self.owner,old_payment_command),old_payment)
                self.assertEqual(accounts.save(self.owner,payment_command),payment)
                self.assertEqual(PayrollAnnualBasis(restored).save(self.owner,annual_command),annual)
                self.assertEqual(_consumption_row(restored,run),proof)
                self.assertEqual(payroll.export(self.owner,run['id'],'pdf')[0],pdf)
                self.assertEqual(payroll.export(self.owner,old['id'],'pdf',revision='1')[0],old_pdf)
                self.assertEqual(bytes(payroll.hr._file(data['file']['id'])['original']),data['original'])
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:restored.db.close()
        finally:
            with psycopg.connect(fixture.DSN,autocommit=True) as operator:operator.execute('DROP DATABASE smartplan_release_check WITH (FORCE)')
        self.reopen()


if __name__=='__main__':unittest.main()
