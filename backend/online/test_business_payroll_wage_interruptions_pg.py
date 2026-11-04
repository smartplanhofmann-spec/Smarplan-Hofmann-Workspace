"""Real U-assessment MFA/HTTP, concurrent PG writers, ACL and dump/restore."""
import calendar
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import tempfile
import threading
import unittest

import psycopg
from psycopg.conninfo import make_conninfo

import business_schema
from business_foundation import BusinessFoundation
from business_payroll_facts import reference
from business_payroll_wage_interruptions import PayrollWageInterruptions,KIND,RULE_VERSION,TABLES
from business_payroll import Payroll
from online import release,test_business_payroll_calculations_pg as calculation_pg
from online.backup import backup
from online.restore import complete_restore,restore
from online.store import PostgresOffice

fixture=calculation_pg.fixture
req=calculation_pg.req


@unittest.skipUnless(fixture.DSN,'Guarded disposable loopback PostgreSQL fixture required')
class WageInterruptionPostgres(unittest.TestCase):
    reopen=calculation_pg.CalculationPayrollPostgres.reopen
    login=calculation_pg.CalculationPayrollPostgres.login
    call=calculation_pg.CalculationPayrollPostgres.call
    sources=calculation_pg.CalculationPayrollPostgres.sources
    setUp=calculation_pg.CalculationPayrollPostgres.setUp

    def workflow(self):
        data=calculation_pg.CalculationPayrollPostgres.workflow(self);employee=data['employee'];file=data['file']
        common=dict(employee_id=employee['id'],employee_revision=employee['revision'],source_file_ids=[file['id']])
        schedule=self.call('POST','/business/payroll/facts',req(**common,kind='work_schedule',revision=0,status='active',confirmed=True,
            details=dict(month='2026-10',days=[dict(date=date(2026,10,n).isoformat(),scheduled_seconds=28800 if date(2026,10,n).weekday()<5 else 0,
                workplace='Actual original contractual workplace',federal_state='BW') for n in range(1,32)],reason='Actual complete contractual daily schedule'))).json
        file_ref=dict(id=file['id'],revision=1,content_hash=file['content_hash'])
        details=dict(case_key=req()['request_id'],employment_terms_ref=data['case']['details']['employment_terms_refs'][0],
            work_schedule_refs=[],preparation_refs=[],agreement_refs=[reference(data['agreement'])],sickness_history_ref=None,
            input=dict(**{'from':'2026-10-15','to':'2026-10-21'},employment_to=None,employment_continues=True,no_wage_claim=True,
                intervening_paid_days=[],evidence_refs=[file_ref],exceptions=[]),verification_note='Actual first five unpaid contractual workdays')
        proposal=dict(common,kind='unpaid_continuation',details=details)
        preview=self.call('POST','/business/payroll/entitlements/preview',proposal).json
        claim=self.call('POST','/business/payroll/entitlements',req(**proposal,revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])).json
        case_input={key:data['case_command'][key] for key in ('employee_id','employee_revision','kind','rule_version','source_contract_version','details','source_file_ids')}
        case_input['details']=dict(case_input['details'],entitlement_case_refs=[reference(claim)])
        preview=self.call('POST','/business/payroll/calculation-cases/preview',case_input).json
        case=self.call('POST','/business/payroll/calculation-cases',req(**case_input,id=data['case']['id'],revision=1,status='active',confirmed=True,
            preview_hash=preview['preview_hash'],correction_reason='Bind actual unpaid original before payroll finalization')).json
        run_input=dict(source_schema_version=3,employee_id=employee['id'],calculation_case_ref=reference(case))
        preview=self.call('POST','/business/payroll/preview',run_input).json
        run_command=req(**run_input,revision=0,confirmed=True,preview_hash=preview['preview_hash'],accepted_scope=preview['calculation']['scope'])
        run=self.call('POST','/business/payroll/runs',run_command).json
        details=dict(year=2026,assessment_through='2026-10-31',employment_terms_refs=case['details']['employment_terms_refs'],
            run_refs=[reference(run)],work_schedule_refs=[reference(schedule)],entitlement_case_refs=[reference(claim)],
            excluded_payments_reviewed=True,exception_review_file_refs=[file_ref],excluded_payments=[],
            verification_note='All eight statutory sentence4 kinds checked in actual employer original')
        input_=dict(common,kind=KIND,rule_version=RULE_VERSION,source_contract_version=1,details=details)
        preview=self.call('POST','/business/payroll/wage-interruptions/preview',input_).json
        self.assertTrue(preview['can_determine']);self.assertEqual(1,preview['plan']['number_u'])
        command=req(**input_,revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        return dict(data,run=run,run_command=run_command,case=case,claim=claim,schedule=schedule,marker_input=input_,marker_command=command)

    def test_actual_mfa_parallel_original_fresh_permissions_and_protected_database(self):
        data=self.workflow();barrier=threading.Barrier(2)
        def writer(_):
            office=PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=10)
                return PayrollWageInterruptions(office).save(self.owner,data['marker_command'])
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(writer,range(2)))
        saved=results[0];self.assertEqual(saved,results[1]);self.assertEqual(1,self.office.db.execute('SELECT COUNT(*) FROM '+TABLES[0]).fetchone()[0])
        self.assertEqual(saved,self.call('POST','/business/payroll/wage-interruptions',data['marker_command']).json)
        self.assertNotIn('accepted_command',saved)
        source=self.call('GET','/business/payroll/wage-interruptions/sources?employee_id='+data['employee']['id']+'&year=2026').json
        self.assertIn(reference(data['schedule']),[reference(value) for value in source['facts']])
        ledger=self.call('GET','/business/payroll/ledger?employee_id='+data['employee']['id']+'&year=2026').json['ledger']
        self.assertEqual(1,ledger['recorded_wage_interruptions']['number_u'])
        self.assertNotIn('unpaid_statutory_marker_requires_evidence',ledger['account_completeness_issues'])
        path='/business/payroll/wage-interruptions/'+saved['id']
        self.call('GET',path,token=data['tech'],status=403)
        offline=self.call('POST','/business/offline/access',{},status=201).json['token']
        self.call('POST','/business/payroll/wage-interruptions',data['marker_command'],token=offline,status=403)
        self.call('GET',path,{},status=400)
        self.call('POST','/business/payroll/wage-interruptions?ignored=1',data['marker_command'],status=400)
        uid=self.call('POST','/users',dict(email='u-reviewer@example.test',password='Synthetic-u-reviewer-password-123',role='accountant'),status=201).json['id']
        token=self.login('u-reviewer@example.test','Synthetic-u-reviewer-password-123');grants=BusinessFoundation(self.office)
        for permission in ('personnel.read','personnel.approve'):
            grants.save_grant(self.owner,req(user_id=uid,permission=permission,scope='*',effect='allow',revision=0))
        correction=data['marker_command']|req(id=saved['id'],revision=1,correction_reason='Independent protected original review')
        updated=self.call('POST','/business/payroll/wage-interruptions',correction,token=token).json
        grants.save_grant(self.owner,req(user_id=uid,permission='personnel.approve',scope='*',effect='deny',revision=1))
        self.call('POST','/business/payroll/wage-interruptions',correction,token=token,status=403)
        self.call('POST','/business/payroll/wage-interruptions',correction|req(),token=token,status=403)
        grants.save_grant(self.owner,req(user_id=uid,permission='personnel.read',scope='*',effect='deny',revision=1))
        self.call('GET',path,token=token,status=403)
        self.reopen();self.assertEqual([saved,updated],self.call('GET',path+'/history').json['items'])
        for table in TABLES:
            column='id' if table.endswith('events') else 'request_id'
            for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table,'TRUNCATE '+table):
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    with self.office.db:self.office.db.execute(statement)
            with psycopg.connect(fixture.DSN,autocommit=True) as operator:
                for statement in ('UPDATE '+table+' SET '+column+'='+column,'DELETE FROM '+table):
                    with self.assertRaisesRegex(psycopg.Error,'immutable payroll wage interruption'):
                        with operator.transaction():operator.execute('SET LOCAL ROLE "smartplan-migrator"');operator.execute(statement)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_actual_backup_restore_preserves_u_run_original_receipt_and_ledger_bytes(self):
        data=self.workflow();saved=self.call('POST','/business/payroll/wage-interruptions',data['marker_command']).json
        ledger=self.call('GET','/business/payroll/ledger?employee_id='+data['employee']['id']+'&year=2026').json['ledger']
        query=dict(employee_id=data['employee']['id'],year='2026',snapshot_hash=ledger['snapshot_hash'])
        pdf=Payroll(self.office).export_ledger(self.owner,query,'pdf')[0]
        self.office.db.close();target=make_conninfo(fixture.DSN,dbname='smartplan_release_check')
        release.validate_dsns(fixture.DSN,target,test_mode=True)
        with psycopg.connect(fixture.DSN,autocommit=True) as operator:
            if operator.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():raise RuntimeError('Existing restore target remains untouched')
            operator.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='synthetic-payroll-u-backup-') as directory:
                archive=backup(fixture.DSN,directory);result=restore(archive,fixture.DSN,target,privileged_operator=True,test_mode=True)
                self.assertTrue(result['restore_pending'])
            runtime=make_conninfo(self.runtime,dbname='smartplan_release_check');verifier=PostgresOffice(runtime,allow_restore_pending=True)
            try:self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally:verifier.db.close()
            restored=PostgresOffice(runtime)
            try:
                api=PayrollWageInterruptions(restored);payroll=Payroll(restored)
                self.assertEqual(saved,api.save(self.owner,data['marker_command']))
                self.assertEqual(data['run'],payroll.finalize(self.owner,data['run_command']))
                current=payroll.ledger(self.owner,dict(employee_id=data['employee']['id'],year='2026'))['ledger']
                self.assertEqual(ledger,current);self.assertEqual(pdf,payroll.export_ledger(self.owner,query,'pdf')[0])
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:restored.db.close()
        finally:
            with psycopg.connect(fixture.DSN,autocommit=True) as operator:operator.execute('DROP DATABASE smartplan_release_check WITH (FORCE)')
        self.reopen()


if __name__=='__main__':unittest.main()
