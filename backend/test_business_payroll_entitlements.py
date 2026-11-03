"""Isolated P4 immutable facts, source binding, rights and historical replay."""
import base64
import calendar
from copy import deepcopy
from datetime import date
import json
import sqlite3
import unittest
from unittest.mock import patch

import business_schema
import business_payroll_entitlements as entitlements
from business_foundation import BusinessFoundation
from business_payroll_facts import reference
from business_personnel_workflow import _sha
from core import canonical
import test_business_payroll_facts as fact_fixture
import test_business_payroll as monthly
import test_payroll_entitlements_2026 as pure_fixture


class PayrollEntitlementTests(monthly.BusinessFixture,unittest.TestCase):
    case=fact_fixture.PayrollFactTests.case
    identity_details=fact_fixture.PayrollFactTests.identity_details
    save_account=fact_fixture.PayrollFactTests.save_account
    account_api=fact_fixture.PayrollFactTests.account_api
    terms_details=fact_fixture.PayrollFactTests.terms_details
    body=fact_fixture.PayrollFactTests.body
    terms=fact_fixture.PayrollFactTests.terms
    pause=fact_fixture.PayrollFactTests.pause

    def setUp(self):
        names=business_schema.MODULE_NAMES
        if 'business_payroll_entitlements' not in names:names+=('business_payroll_entitlements',)
        self.registry=patch.object(business_schema,'MODULE_NAMES',names)
        self.registry.start();self.addCleanup(self.registry.stop)
        fact_fixture.PayrollFactTests.setUp(self)
        self.terms_record,_=self.terms()
        self.claims=entitlements.PayrollEntitlements(self.office,clock=lambda:self.now)
        self.original=dict(id=self.data['file']['id'],revision=1,content_hash=self.data['file']['content_hash'])

    def details(self,kind='unpaid_continuation'):
        source=dict(**{'from':'2026-10-20','to':'2026-12-15'},employment_to=None,employment_continues=True,
            no_wage_claim=True,intervening_paid_days=[],evidence_refs=[self.original],exceptions=[])
        if kind=='sickness_history':
            source=dict(employment_from='2026-10-15',employment_to=None,pay_basis='monthly',
                complete_from='2026-10-15',complete_through='2026-12-31',history_evidence_refs=[self.original],
                episodes=[dict(id=monthly.rid(),**{'from':'2026-10-20','to':'2026-12-31'},onset='before_work',
                    first_scheduled_day=None,continuation_group=monthly.rid(),recovery_before=True,unculpable=True,evidence_refs=[self.original])])
        return dict(case_key=monthly.rid(),employment_terms_ref=reference(self.terms_record),work_schedule_refs=[],
            preparation_refs=[],agreement_refs=[reference(self.data['agreement'])],sickness_history_ref=None,
            input=source,verification_note='Synthetische vollständige private Originalentscheidung ohne Diagnose')

    def request(self,kind='unpaid_continuation',details=None):
        preview=dict(employee_id=self.employee['id'],employee_revision=self.employee['revision'],kind=kind,
            details=details or self.details(kind),source_file_ids=[self.data['file']['id']])
        proposed=self.claims.preview(self.owner,preview)
        return dict(preview,request_id=monthly.rid(),revision=0,status='active',confirmed=True,preview_hash=proposed['preview_hash']),proposed

    def save(self,kind='unpaid_continuation',details=None):
        body,preview=self.request(kind,details)
        return self.claims.save(self.owner,body),body,preview

    def test_actual_private_fact_and_exact_replay_do_not_create_payroll_or_payment(self):
        before={name:self.office.db.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in ('business_payroll_events','business_payroll_cash_batches','business_euer_entries')}
        saved,body,preview=self.save()
        self.assertEqual(preview['plan'],saved['plan']);self.assertEqual(self.claims.save(self.owner,body),saved)
        self.assertEqual(self.claims.resolve_entitlement_case(self.owner,self.employee['id'],reference(saved)),saved)
        self.assertEqual('2026-11-19',saved['plan']['continuation_windows'][0]['statutory_deadline'])
        self.assertEqual(self.claims.get(self.owner,saved['id'],True)['items'],[saved])
        self.assertTrue(entitlements.validate_integrity(self.office))
        self.assertEqual(before,{name:self.office.db.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in before})

    def test_sickness_waiting_period_uses_employee_original_and_preserves_no_diagnosis(self):
        saved,_,_=self.save('sickness_history')
        episode=saved['plan']['episodes'][0]
        self.assertEqual(('2026-11-12','2026-12-23'),(episode['entitlement_from'],episode['entitlement_to']))
        self.assertTrue(entitlements.validate_integrity(self.office))
        self.assertNotIn('medical',canonical(saved['sources']))

    def test_real_source_hash_forgery_and_foreign_original_are_not_accepted(self):
        details=self.details();details['input']['evidence_refs'][0]=dict(self.original,content_hash='0'*64)
        self.problem(409,lambda:self.request(details=details))
        details=self.details();details['input']['evidence_refs'][0]=dict(self.original,id='f'*32)
        self.problem(409,lambda:self.request(details=details))

    def test_correction_void_and_lost_ack_preserve_original_and_module_pause(self):
        saved,body,_=self.save()
        changed=deepcopy(body);changed.update(request_id=monthly.rid(),id=saved['id'],revision=1,correction_reason='Belegten Vermerk präzisiert')
        changed['details']['verification_note']='Neue belegte Fassung'
        preview=self.claims.preview(self.owner,{key:changed[key] for key in ('employee_id','employee_revision','kind','details','source_file_ids')})
        changed['preview_hash']=preview['preview_hash'];revision=self.claims.save(self.owner,changed)
        self.assertEqual(2,revision['revision']);self.assertEqual(saved,self.claims.save(self.owner,body))
        self.employee=self.call(self.planning,'save_employee',self.owner,dict(request_id=monthly.rid(),id=self.employee['id'],revision=self.employee['revision'],name='Geänderter Name'))
        archived=self.claims.save(self.owner,changed|dict(request_id=monthly.rid(),revision=2,status='void',
            employee_revision=self.employee['revision'],correction_reason='Anspruch zurückgenommen'))
        self.assertEqual(3,archived['revision']);self.assertEqual(revision['sources'],archived['sources'])
        self.pause();self.assertEqual(saved,self.claims.save(self.owner,body));self.assertEqual(revision,self.claims.save(self.owner,changed))
        self.problem(423,lambda:self.claims.save(self.owner,body|dict(request_id=monthly.rid())))
        self.assertTrue(entitlements.validate_integrity(self.office))

    def test_accepted_approval_requires_fresh_private_read_and_approval(self):
        uid=self.office.add_user('entitlement-delegate@example.test','Synthetic-Entitlement-password-123','technician')
        actor=dict(id=uid,email='entitlement-delegate@example.test',role='technician');grants=BusinessFoundation(self.office)
        for name in ('personnel.read','personnel.approve'):
            grants.save_grant(self.owner,dict(request_id=monthly.rid(),user_id=uid,permission=name,scope='*',effect='allow',revision=0))
        body,_=self.request();saved=self.claims.save(actor,body);self.assertEqual(saved,self.claims.save(actor,body))
        grants.save_grant(self.owner,dict(request_id=monthly.rid(),user_id=uid,permission='personnel.read',scope='*',effect='deny',revision=1))
        for action in (lambda:self.claims.save(actor,body),lambda:self.claims.get(actor,saved['id']),lambda:self.claims.sources(actor,dict(employee_id=self.employee['id']))):self.problem(403,action)

    def test_superseded_file_blocks_new_use_but_not_accepted_original(self):
        saved,body,_=self.save()
        self.hr.upload(self.owner,dict(request_id=monthly.rid(),employee_id=self.employee['id'],purpose='personnel',owner_visible=False,
            filename='superseded-original.pdf',media_type='application/pdf',supersedes=self.data['file']['id'],
            content_base64=base64.b64encode(b'%PDF-1.4\nSynthetic newer original\n%%EOF').decode()))
        self.problem(409,lambda:self.claims.resolve_entitlement_case(self.owner,self.employee['id'],reference(saved)))
        self.assertEqual(saved,self.claims.save(self.owner,body));self.assertTrue(entitlements.validate_integrity(self.office))

    def test_new_actual_agreement_cannot_be_omitted_from_new_fact_sources(self):
        saved,body,_=self.save()
        self.hr.save_agreement(self.owner,dict(request_id=monthly.rid(),employee_id=self.employee['id'],revision=0,
            effective_from='2026-11-01',employment_kind='minijob',pay_basis='monthly',amount_minor=59000,currency='EUR',reference_file_id=self.data['file']['id']))
        self.problem(409,lambda:self.request(details=self.details()))
        self.problem(409,lambda:self.claims.resolve_entitlement_case(self.owner,self.employee['id'],reference(saved)))
        self.assertEqual(saved,self.claims.save(self.owner,body));self.assertTrue(entitlements.validate_integrity(self.office))

    def test_immutable_tables_and_receipt_conflict(self):
        saved,body,_=self.save()
        self.problem(409,lambda:self.claims.save(self.owner,body|dict(correction_reason='Different original request')))
        for table in entitlements.TABLES:
            with self.assertRaises(sqlite3.IntegrityError):self.office.db.execute('DELETE FROM '+table)
        with self.assertRaises(sqlite3.IntegrityError):
            self.office.db.execute("UPDATE business_payroll_entitlement_events SET status='void' WHERE id=?",(saved['id'],))

    def test_route_dispatch_shape_and_sources_private_original_refs(self):
        data,status,media=entitlements.dispatch(self.office,self.owner,'/payroll/entitlements/sources','GET',dict(_query=dict(employee_id=self.employee['id'])))
        self.assertEqual((200,'application/json'),(status,media));self.assertIn(self.original,data['file_references'])
        self.assertEqual([],data['entitlements'])
        self.problem(405,lambda:entitlements.dispatch(self.office,self.owner,'/payroll/entitlements','DELETE',{}))

    def test_missing_plan_preparation_and_unverified_sickness_bool_are_blocked(self):
        details=self.details();details['input']=dict(kind='sickness',hourly_rate_minor=1800,evidence_refs=[self.original],
            days=[dict(date='2026-10-20',scheduled_regular_seconds=28800,worked_regular_seconds=0,
                entitled=True,absence_is_only_cause=True,holiday_adjacent_unexcused=None,evidence_refs=[self.original])])
        self.problem(409,lambda:self.request('regular_absence',details))

    def hourly(self):
        agreement=self.data['agreement']
        self.data['agreement']=self.hr.save_agreement(self.owner,dict(request_id=monthly.rid(),employee_id=self.employee['id'],
            id=agreement['id'],revision=agreement['revision'],effective_from=agreement['effective_from'],employment_kind='minijob',
            pay_basis='hourly',amount_minor=1800,currency='EUR',reference_file_id=self.data['file']['id'],correction_reason='Tatsächlich vereinbarten Stundenlohn belegt'))
        self.terms_record=self.api.save(self.owner,self.body('employment_terms',self.terms_details(),id=self.terms_record['id'],
            revision=self.terms_record['revision'],correction_reason='Stundenlohnvereinbarung konkret gebunden'))

    def schedule(self,month):
        first=date.fromisoformat(month+'-01')
        details=dict(month=month,days=[dict(date=date(first.year,first.month,n).isoformat(),
            scheduled_seconds=28800 if date(first.year,first.month,n).weekday()<5 else 0,
            workplace='Belegter synthetischer Arbeitsort',federal_state='BW') for n in range(1,calendar.monthrange(first.year,first.month)[1]+1)],reason='Belegter regelmäßiger Wochenplan')
        return self.api.save(self.owner,self.body('work_schedule',details))

    def absence_preparation(self,first,last,kind):
        absence=self.call(self.planning,'save_absence',self.technician,dict(request_id=monthly.rid(),employee_id=self.employee['id'],
            start_date=first,end_date=last,kind=kind,details='Private Information darf nicht im Anspruch erscheinen'))
        self.call(self.planning,'approve_absence',self.owner,absence['id'],dict(request_id=monthly.rid(),revision=absence['revision'],status='approved'))
        preview=self.hr.preview(self.owner,dict(employee_id=self.employee['id'],month=first[:7]))
        prior=self.data['preparation'] if self.data['preparation']['month']==first[:7] else None
        return self.hr.close_preparation(self.owner,dict(request_id=monthly.rid(),employee_id=self.employee['id'],month=first[:7],
            revision=prior['revision'] if prior else 0,source_hash=preview['source_hash'],completeness_confirmed=True,
            **(dict(id=prior['id'],correction_reason='Tatsächliche Abwesenheitsquelle ergänzt') if prior else {})))

    def test_actual_hourly_sickness_binds_history_schedule_absence_and_contract(self):
        self.hourly();details=self.details('sickness_history');details['input']['pay_basis']='hourly'
        history,_,_=self.save('sickness_history',details)
        schedule=self.schedule('2026-11');preparation=self.absence_preparation('2026-11-16','2026-11-16','sick')
        details=self.details();details.update(work_schedule_refs=[reference(schedule)],preparation_refs=[reference(preparation)],sickness_history_ref=reference(history))
        details['input']=dict(kind='sickness',hourly_rate_minor=1800,evidence_refs=[self.original],
            days=[dict(date='2026-11-16',scheduled_regular_seconds=28800,worked_regular_seconds=0,
                entitled=True,absence_is_only_cause=True,holiday_adjacent_unexcused=None,evidence_refs=[self.original])])
        saved,body,_=self.save('regular_absence',details)
        self.assertEqual((14400,28800),(saved['plan']['gross_minor'],saved['plan']['paid_absence_seconds']))
        self.assertNotIn('Private Information',canonical(saved['sources']))
        for field,bad_value in (('scheduled_regular_seconds',14400),('entitled',False),('worked_regular_seconds',1)):
            wrong=deepcopy(details);wrong['input']['days'][0][field]=bad_value
            self.problem(409,lambda:self.request('regular_absence',wrong))
        wrong=deepcopy(details);wrong['input']['hourly_rate_minor']=1801
        self.problem(409,lambda:self.request('regular_absence',wrong))
        self.assertTrue(entitlements.validate_integrity(self.office));self.assertEqual(saved,self.claims.save(self.owner,body))

    def test_sickness_after_calculated_entitlement_cannot_be_forced_paid(self):
        self.hourly();details=self.details('sickness_history');details['input']['pay_basis']='hourly'
        history,_,_=self.save('sickness_history',details)
        schedule=self.schedule('2026-12');preparation=self.absence_preparation('2026-12-28','2026-12-28','sick')
        details=self.details();details.update(work_schedule_refs=[reference(schedule)],preparation_refs=[reference(preparation)],sickness_history_ref=reference(history))
        details['input']=dict(kind='sickness',hourly_rate_minor=1800,evidence_refs=[self.original],
            days=[dict(date='2026-12-28',scheduled_regular_seconds=28800,worked_regular_seconds=0,
                entitled=True,absence_is_only_cause=True,holiday_adjacent_unexcused=None,evidence_refs=[self.original])])
        self.problem(409,lambda:self.request('regular_absence',details))
        details['input']['days'][0]['entitled']=False
        saved,_,_=self.save('regular_absence',details);self.assertEqual(0,saved['plan']['gross_minor'])

    def test_actual_worked_first_sickness_day_keeps_project_time_and_pays_only_remainder(self):
        from business_time import TimeTracking
        self.hourly();self.now=self.now.replace(month=11,day=17)
        time=TimeTracking(self.office,clock=lambda:self.now);entry_id=monthly.rid()
        base=dict(entry_id=entry_id,device_id='synthetic-entitlement-device',project_id=self.project)
        self.call(time,'event',self.technician,dict(base,request_id=monthly.rid(),sequence=1,revision=0,action='start',occurred_at='2026-11-16T08:00:00+01:00'))
        self.call(time,'event',self.technician,dict(base,request_id=monthly.rid(),sequence=2,revision=1,action='stop',occurred_at='2026-11-16T12:00:00+01:00'))
        summary=self.call(time,'summary',self.owner,dict(employee_id=self.employee['id'],**{'from':'2026-11-16','to':'2026-11-16'}))
        self.call(time,'approve_day',self.owner,'2026-11-16',dict(request_id=monthly.rid(),employee_id=self.employee['id'],revision=summary['days'][0]['revision']))
        schedule=self.schedule('2026-11');preparation=self.absence_preparation('2026-11-16','2026-11-17','sick')
        details=self.details('sickness_history');details['input']['pay_basis']='hourly'
        details['input']['episodes'][0].update(**{'from':'2026-11-16','to':'2026-11-17'},onset='during_work')
        history,_,_=self.save('sickness_history',details)
        details=self.details();details.update(work_schedule_refs=[reference(schedule)],preparation_refs=[reference(preparation)],sickness_history_ref=reference(history))
        details['input']=dict(kind='first_sickness_day_regular_wage',hourly_rate_minor=1800,evidence_refs=[self.original],
            days=[dict(date='2026-11-16',scheduled_regular_seconds=28800,worked_regular_seconds=14400,
                entitled=True,absence_is_only_cause=True,holiday_adjacent_unexcused=None,evidence_refs=[self.original])])
        before=[dict(row) for row in self.office.db.execute('SELECT * FROM business_time_days')]
        saved,_,_=self.save('regular_absence',details)
        self.assertEqual((7200,14400),(saved['plan']['gross_minor'],saved['plan']['paid_absence_seconds']))
        self.assertEqual(before,[dict(row) for row in self.office.db.execute('SELECT * FROM business_time_days')])
        self.assertEqual(14400,saved['plan']['days'][0]['actual_work_seconds'])

    def test_public_holiday_uses_workplace_state_and_bank_holiday_is_not_accepted(self):
        self.hourly();schedule=self.schedule('2026-12')
        preview=self.hr.preview(self.owner,dict(employee_id=self.employee['id'],month='2026-12'))
        preparation=self.hr.close_preparation(self.owner,dict(request_id=monthly.rid(),employee_id=self.employee['id'],month='2026-12',
            revision=0,source_hash=preview['source_hash'],completeness_confirmed=True))
        details=self.details();details.update(work_schedule_refs=[reference(schedule)],preparation_refs=[reference(preparation)])
        details['input']=dict(kind='public_holiday',hourly_rate_minor=1800,evidence_refs=[self.original],
            days=[dict(date='2026-12-25',scheduled_regular_seconds=28800,worked_regular_seconds=0,
                entitled=True,absence_is_only_cause=True,holiday_adjacent_unexcused=False,evidence_refs=[self.original])])
        saved,_,_=self.save('regular_absence',details)
        self.assertEqual(14400,saved['plan']['gross_minor']);self.assertIsNotNone(saved['sources']['holiday_calendar_hash'])
        wrong=deepcopy(details);wrong['input']['days'][0]['date']='2026-12-24'
        self.problem(409,lambda:self.request('regular_absence',wrong))

    def test_vacation_uses_all_thirteen_weeks_plans_and_actual_approved_vacation(self):
        self.employee=self.call(self.planning,'save_employee',self.owner,dict(request_id=monthly.rid(),id=self.employee['id'],
            revision=self.employee['revision'],employment_from='2026-01-01'))
        self.api.save(self.owner,self.body('employment_terms',self.terms_record['details'],id=self.terms_record['id'],revision=1,
            status='void',correction_reason='Tatsächlichen früheren Beschäftigungsbeginn belegt'))
        agreement=self.data['agreement']
        self.data['agreement']=self.hr.save_agreement(self.owner,dict(request_id=monthly.rid(),employee_id=self.employee['id'],
            id=agreement['id'],revision=agreement['revision'],effective_from=agreement['effective_from'],employment_kind='minijob',
            pay_basis='hourly',amount_minor=1800,currency='EUR',reference_file_id=self.data['file']['id'],correction_reason='Stundenvertrag belegt'))
        self.terms_record=self.api.save(self.owner,self.body('employment_terms',self.terms_details()|dict(employment_from='2026-01-01')))
        schedules=[self.schedule(month) for month in ('2026-07','2026-08','2026-09','2026-10')]
        preparation=self.absence_preparation('2026-10-05','2026-10-09','vacation')
        source=pure_fixture.vacation()
        def replace_refs(value):
            if isinstance(value,dict):
                for key,item in value.items():
                    if key=='evidence_refs':value[key]=[self.original]
                    else:replace_refs(item)
            elif isinstance(value,list):
                for item in value:replace_refs(item)
        replace_refs(source)
        details=self.details();details.update(work_schedule_refs=[reference(item) for item in schedules],
            preparation_refs=[reference(preparation)],input=source)
        saved,_,_=self.save('vacation_reference',details)
        self.assertEqual(50000,saved['plan']['gross_minor']);self.assertTrue(entitlements.validate_integrity(self.office))
        wrong=deepcopy(details);wrong['work_schedule_refs'].pop(0)
        self.problem(409,lambda:self.request('vacation_reference',wrong))

    def test_restore_detects_rehashed_employee_binding_even_with_rehashed_plan_and_receipt(self):
        saved,body,_=self.save()
        table='business_payroll_entitlement_events'
        self.office.db.execute('DROP TRIGGER '+table+'_update_guard')
        self.office.db.execute('DROP TRIGGER business_payroll_entitlement_requests_update_guard')
        row=dict(self.claims._row(saved['id']));sources=json.loads(row['sources_json']);payload=json.loads(row['payload_json'])
        sources['employee']['user_id']=self.owner['id']
        payload['plan']=entitlements.build_entitlement_plan(sources)
        payload['preview_hash']=_sha(dict(source_snapshot=sources,plan=payload['plan']))
        envelope={key:value for key,value in row.items() if key not in ('payload_json','sources_json','content_hash')}
        envelope.update(source_hash=_sha(sources),payload=payload,sources=sources);digest=_sha(envelope)
        self.office.db.execute('UPDATE '+table+' SET sources_json=?,payload_json=?,source_hash=?,content_hash=? WHERE id=?',
            (canonical(sources),canonical(payload),_sha(sources),digest,saved['id']))
        self.office.db.execute('UPDATE business_payroll_entitlement_requests SET fact_content_hash=? WHERE fact_id=?',(digest,saved['id']))
        with self.assertRaises(ValueError):entitlements.validate_integrity(self.office)
        self.problem(500,lambda:self.claims.save(self.owner,body))

    def test_exact_accepted_body_is_private_and_independently_hash_bound(self):
        saved,body,_=self.save()
        row=dict(self.claims._row(saved['id']))
        payload=json.loads(row['payload_json'])
        self.assertEqual(body,payload['accepted_command'])
        self.assertNotIn('accepted_command',saved)
        self.assertNotIn('accepted_command',self.claims.get(self.owner,saved['id']))
        payload['accepted_command']['employee_revision']+=1
        envelope={key:value for key,value in row.items() if key not in ('payload_json','sources_json','content_hash')}
        envelope.update(payload=payload,sources=json.loads(row['sources_json']))
        digest=_sha(envelope)
        self.office.db.execute('DROP TRIGGER business_payroll_entitlement_events_update_guard')
        self.office.db.execute('DROP TRIGGER business_payroll_entitlement_requests_update_guard')
        self.office.db.execute('UPDATE business_payroll_entitlement_events SET payload_json=?,content_hash=? WHERE id=?',
            (canonical(payload),digest,saved['id']))
        self.office.db.execute('UPDATE business_payroll_entitlement_requests SET fact_content_hash=? WHERE fact_id=?',(digest,saved['id']))
        with self.assertRaises(ValueError):entitlements.validate_integrity(self.office)
        with self.assertRaises((entitlements.Problem,ValueError)):self.claims.save(self.owner,body)


if __name__=='__main__':unittest.main()
