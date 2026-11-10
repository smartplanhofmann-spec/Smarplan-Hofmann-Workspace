"""Actual private evidence, full original revision prefix and exact RV receipts."""
from copy import deepcopy
from datetime import datetime,timezone
import sqlite3
import base64
import unittest

from core import Problem
from business_payroll_facts import reference
from business_payroll_rv_lifecycle import PayrollRvLifecycle,RULE_VERSION,KIND,TABLES
import test_business_payroll as original_payroll
rid=original_payroll.rid
from test_payroll_minijob_rv_lifecycle_2026 import request,settled


class RvLifecycleFixture(unittest.TestCase):
    def setUp(self):
        self.parent=original_payroll.PayrollWorkflowTests('runTest');self.parent.setUp();self.addCleanup(self.parent.doCleanups)
        self.f=f=self.parent
        f.now=datetime(2026,10,31,20,tzinfo=timezone.utc)
        f.employee=f.call(f.planning,'save_employee',f.owner,dict(request_id=rid(),id=f.employee['id'],revision=f.employee['revision'],employment_from='2026-01-01',employment_to=None))
        self.data=f.case(minijob_rv_exempt=True)
        self.api=PayrollRvLifecycle(f.office,clock=lambda:f.now)
        self.file=dict(id=self.data['file']['id'],revision=1,content_hash=self.data['file']['content_hash'])

    def body(self):
        f=self.f
        assessment=dict(schema_version=1,employee_id=f.employee['id'],episode_id=f.employee['id'],employment_from='2026-01-01',employment_to=None,
            target_month='2026-10',reviewed_as_of='2026-10-31',sole_continuous_commercial_minijob_confirmed=True,
            no_old_age_or_other_exclusion_confirmed=True,established_exemption=dict(effective_from='2026-01-01',profile_ref=reference(self.data['profile']),
                evidence_ref=self.file,established_status_confirmed=True),revocation=None,review_note='Synthetic actual established exemption and complete employment episode')
        return dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind=KIND,rule_version=RULE_VERSION,
            source_contract_version=1,details=dict(assessment=assessment,prior_assessment_refs=[]),source_file_ids=[self.file['id']])

    def save(self,body,previous=None):
        preview=self.api.preview(self.f.owner,body)
        command=dict(body,request_id=rid(),revision=previous['revision'] if previous else 0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        if previous:command.update(id=previous['id'],correction_reason='Synthetic actual next original procedure state')
        return self.api.save(self.f.owner,command),command

    def add_personal_originals(self,count):
        for i in range(count):
            self.f.hr.upload(self.f.owner,dict(request_id=rid(),employee_id=self.f.employee['id'],purpose='personnel',
                owner_visible=False,filename=f'synthetic-additional-personal-original-{i:03d}.pdf',media_type='application/pdf',
                content_base64=base64.b64encode(f'%PDF-1.4\nSynthetic unrelated personal original {i}\n%%EOF'.encode()).decode()))


class RvLifecycleWorkflow(RvLifecycleFixture):
    def test_actual_initial_and_settled_revocation_keep_original_profile_history_and_exact_receipt(self):
        f=self.f;body=self.body();before=deepcopy(self.data['profile'])
        first,original=self.save(body)
        self.assertTrue(first['plan']['minijob_rv_exempt'])
        body=deepcopy(body);settled(body['details']['assessment']);body['details']['prior_assessment_refs']=[reference(first)]
        current,command=self.save(body,first)
        self.assertEqual(current['previous_hash'],first['content_hash']);self.assertFalse(current['plan']['minijob_rv_exempt'])
        self.assertEqual(current['plan']['candidate_effective_from'],'2026-08-01')
        self.assertEqual(self.api.save(f.owner,original),first);self.assertEqual(self.api.save(f.owner,command),current)
        self.assertEqual(self.api.get(f.owner,first['id'],history=True)['items'],[first,current])
        self.assertEqual(f.payroll.records(f.owner,'profile',dict(employee_id=f.employee['id']))['items'],[before])
        self.assertEqual(f.office.db.execute("SELECT count(*) AS n FROM business_payroll_events WHERE kind='run'").fetchone()['n'],0)
        from business_schema import validate_integrity
        self.assertTrue(validate_integrity(f.office))

    def test_pending_notification_is_saved_as_unresolved_without_financial_or_profile_side_effect(self):
        body=self.body();request(body['details']['assessment']);record,_=self.save(body)
        self.assertFalse(record['plan']['can_bind_payroll']);self.assertIsNone(record['plan']['minijob_rv_exempt'])
        for name in ('creates_profile','payment_created','external_transmission','official_system_approval'):self.assertIs(record['plan'][name],False)

    def test_every_known_revision_is_required_and_duplicate_episode_or_reset_is_rejected(self):
        first,_=self.save(self.body());body=self.body();request(body['details']['assessment']);body['details']['prior_assessment_refs']=[reference(first)]
        second,_=self.save(body,first)
        missing=deepcopy(body);missing['details']['prior_assessment_refs']=[reference(second)]
        with self.assertRaises(Problem) as error:self.api.preview(self.f.owner,missing)
        self.assertEqual(error.exception.status,409)
        reset=self.body();reset['details']['prior_assessment_refs']=[reference(first),reference(second)]
        with self.assertRaises(Problem):self.api.preview(self.f.owner,reset)
        complete=deepcopy(body);complete['details']['prior_assessment_refs']=[reference(first),reference(second)]
        third,_=self.save(complete,second)
        self.assertEqual(third['revision'],3)
        with self.assertRaises(Problem) as error:self.save(complete)
        self.assertEqual(error.exception.status,409)

    def test_fresh_private_rights_are_required_before_receipt_and_sources(self):
        first,command=self.save(self.body())
        for action in [lambda:self.api.sources(self.f.technician,dict(employee_id=self.f.employee['id'])),
                lambda:self.api.get(self.f.technician,first['id']),lambda:self.api.save(self.f.technician,command)]:
            with self.assertRaises(Problem) as error:action()
            self.assertEqual(error.exception.status,403)

    def test_stale_preview_foreign_evidence_and_false_employee_episode_never_write(self):
        body=self.body()
        for mutate in [lambda v:v['details']['assessment'].update(episode_id='f'*32),
                lambda v:v['details']['assessment']['established_exemption']['evidence_ref'].update(content_hash='f'*64),
                lambda v:v['details']['assessment'].update(reviewed_as_of='2026-11-01')]:
            changed=deepcopy(body);mutate(changed)
            with self.assertRaises(Problem):self.api.preview(self.f.owner,changed)
        preview=self.api.preview(self.f.owner,body)
        command=dict(body,request_id=rid(),revision=0,status='active',confirmed=True,preview_hash='f'*64)
        with self.assertRaises(Problem) as error:self.api.save(self.f.owner,command)
        self.assertEqual(error.exception.status,409)
        self.assertEqual(self.f.office.db.execute('SELECT count(*) AS n FROM '+TABLES[0]).fetchone()['n'],0)

    def test_sql_guards_reject_altering_and_deleting_original_state(self):
        value,_=self.save(self.body())
        for sql in ('UPDATE '+TABLES[0]+" SET status='void' WHERE id=?",'DELETE FROM '+TABLES[0]+' WHERE id=?'):
            with self.assertRaises(sqlite3.IntegrityError):self.f.office.db.execute(sql,(value['id'],))
        self.assertEqual(self.api.get(self.f.owner,value['id']),value)


if __name__=='__main__':unittest.main()
