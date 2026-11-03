"""Synthetic customer cases through native inquiry, dispatch and signed service."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import uuid

from core import Office,Problem
from business_service import Service,validate_integrity,protected_tables,dispatch
from business_foundation import BusinessFoundation
from business_organization import Organization
from inquiries import Inquiries


def req(**values):return dict(request_id=uuid.uuid4().hex,**values)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='synthetic-service-');self.addCleanup(self.tmp.cleanup)
        self.office=Office(Path(self.tmp.name)/'office.db');self.addCleanup(self.office.db.close)
        self.owner=dict(id=self.office.add_user('service-owner@example.test','Synthetic-service-owner-password','owner'),role='owner')
        self.manager=dict(id=self.office.add_user('service-manager@example.test','Synthetic-service-manager-password','manager'),role='manager')
        self.api=Service(self.office,clock=lambda:datetime(2026,11,3,12,tzinfo=timezone.utc))
        self.foundation=BusinessFoundation(self.office)
        self.customer=self.foundation.save_contact(self.owner,req(name='Synthetic service customer',persons=[dict(name='Synthetic contact',role_label='Site',email='contact@example.test',phone='')]))
        self.project=self.office.add_project(self.owner,'Synthetic service project',customer_id=self.customer['id'])
        self.office.assign(self.owner,self.project,self.manager['id'])
    def problem(self,status,fn,*args,**kwargs):
        with self.assertRaises(Problem) as caught:fn(*args,**kwargs)
        self.assertEqual(caught.exception.status,status,caught.exception.message)
        return caught.exception
    def values(self,**changes):
        value=dict(revision=0,customer_id=self.customer['id'],person_id=self.customer['persons'][0]['id'],project_id=self.project,
            asset_id=None,contract_id=None,visit_id=None,inquiry_id=None,defect_id=None,title='Synthetic customer complaint',kind='complaint',priority='high',
            responsible_id=self.manager['id'],follow_up_on='2026-11-02',description='Synthetic device inspection requested')
        value.update(changes);return req(**value)
    def create(self,**changes):return self.api.save(self.owner,self.values(**changes))
    def command_body(self,item,**extra):
        current=self.api.view(self.owner,item['id']);return req(revision=current['revision'],source_sha256=current['source_sha256'],**extra)
    def command(self,item,action,**extra):return self.api.command(self.owner,item['id'],action,self.command_body(item,**extra))
    def transition(self,item,status):return self.command(item,'transition',status=status,reason='Synthetic recorded decision '+status,resolution='Synthetic verified resolution' if status in ('resolved','closed') else '')
    def appointment(self,item,**changes):
        value=dict(confirmation=True,title='Synthetic service visit',start_at='2026-11-04T09:00:00+01:00',end_at='2026-11-04T10:00:00+01:00',timezone='Europe/Berlin',employee_ids=[],resource_ids=[],details='Synthetic dispatch')
        value.update(changes);return self.command(item,'dispatch',**value)
    def report(self,project=None):
        project=project or self.project
        draft=self.api.ops.save_entry(self.owner,project,'service',req(title='Synthetic signed service',description='Synthetic work verified'))
        return self.api.ops.sign_entry(self.owner,project,draft['id'],req(revision=draft['revision'],expected_hash=draft['content_hash'],signer='Synthetic customer',strokes=[[[0.1,0.2],[0.8,0.6]]]))

    def test_inquiry_to_single_canonical_project_dispatch_resolution_close_and_reopen(self):
        inquiry=Inquiries(self.office).create(self.owner,req(subject='Synthetic service inquiry',message='Synthetic repair request',sender_email='customer@example.test'))
        create_body=self.values(project_id=None,responsible_id=self.owner['id'],inquiry_id=inquiry['id'])
        item=self.api.save(self.owner,create_body)
        body=self.command_body(item,confirmation=True,project_id=None,project_name='Canonical converted service project')
        result=self.api.command(self.owner,item['id'],'project',body)
        self.assertEqual(self.api.command(self.owner,item['id'],'project',body),result)
        project=result['case']['project_id'];self.assertEqual(Inquiries(self.office).get(self.owner,inquiry['id'])['project_id'],project)
        self.assertEqual(self.api.save(self.owner,create_body),item)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM projects').fetchone()[0],2)
        self.transition(item,'triaged');dispatched=self.appointment(item)
        self.assertEqual(dispatched['case']['status'],'planned')
        self.assertEqual(dispatched['link']['source_snapshot']['project_id'],project)
        self.command(item,'evidence',confirmation=True,report_id=self.report(project)['id'])
        self.transition(item,'resolved');self.transition(item,'closed');reopened=self.transition(item,'triaged')
        self.assertEqual(reopened['case']['status'],'triaged')
        history=self.api.history(self.owner,item['id'])
        self.assertIn('closed',[v['status'] for v in history['versions']])
        self.assertEqual([v['ordinal'] for v in history['events']],list(range(1,len(history['events'])+1)))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_documents').fetchone()[0],0)
        validate_integrity(self.office)

    def test_maintenance_uses_existing_visit_and_frozen_native_report_completion(self):
        asset=self.api.maintenance.save_asset(self.owner,self.project,req(name='Synthetic equipment',serial_number='SYN-SERVICE-1'))
        contract=self.api.maintenance.save_contract(self.owner,self.project,req(asset_id=asset['id'],title='Synthetic contract',anchor_date='2026-11-01',interval_unit='months',interval_count=1))
        visit=self.api.maintenance.schedule_due(self.owner,req(project_id=self.project,as_of='2026-11-01'))['items'][0]
        item=self.create(kind='maintenance',visit_id=visit['id'])
        self.assertEqual((item['asset_id'],item['contract_id']),(asset['id'],contract['id']))
        self.transition(item,'triaged')
        self.problem(409,self.api.command,self.owner,item['id'],'transition',self.command_body(item,status='resolved',reason='Attempt premature completion',resolution='Unsupported claim'))
        report=self.report();body=self.command_body(item,confirmation=True,report_id=report['id'])
        linked=self.api.command(self.owner,item['id'],'evidence',body)
        self.assertEqual(self.api.command(self.owner,item['id'],'evidence',body),linked)
        completed=self.api.maintenance.history(self.owner,self.project)[0]
        self.assertEqual((completed['status'],completed['report_pdf_sha256']),('completed',report['pdf_sha256']))
        self.assertEqual(self.transition(item,'resolved')['case']['status'],'resolved')
        validate_integrity(self.office)

    def test_foreign_and_duplicate_origins_or_unsignable_evidence_are_rejected(self):
        defect=self.api.ops.save_entry(self.owner,self.project,'defect',req(title='Synthetic defect',details='Observed defect'))
        item=self.create(defect_id=defect['id']);self.problem(409,self.api.save,self.owner,self.values(defect_id=defect['id']))
        foreign=self.foundation.save_contact(self.owner,req(name='Foreign synthetic customer'))
        other=self.office.add_project(self.owner,'Foreign service project',customer_id=foreign['id'])
        self.problem(409,self.api.save,self.owner,self.values(customer_id=foreign['id'],person_id=None))
        self.problem(404,self.api.command,self.owner,item['id'],'evidence',self.command_body(item,confirmation=True,report_id=self.report(other)['id']))
        draft=self.api.ops.save_entry(self.owner,self.project,'service',req(title='Draft report'))
        self.problem(409,self.api.command,self.owner,item['id'],'evidence',self.command_body(item,confirmation=True,report_id=draft['id']))

    def test_existing_inquiry_conversion_is_reused_after_other_workflow_completed_it(self):
        inquiries=Inquiries(self.office)
        inquiry=inquiries.create(self.owner,req(subject='Synthetic shared inquiry',message='Synthetic follow up',sender_email='same@example.test'))
        item=self.create(project_id=None,responsible_id=self.owner['id'],inquiry_id=inquiry['id'])
        converted=inquiries.convert(self.owner,inquiry['id'],req(revision=inquiry['revision'],project_name='Already canonical project',customer_id=self.customer['id']))
        result=self.command(item,'project',confirmation=True,project_id=None,project_name='Must not create another')
        self.assertEqual(result['case']['project_id'],converted['project']['id'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM projects').fetchone()[0],2)

    def test_stale_sources_and_stale_versions_cannot_apply_decisions(self):
        item=self.create();body=self.command_body(item,status='triaged',reason='Earlier reviewed source',resolution='')
        self.assertEqual(self.api.listing(self.owner,{'priority':'high','responsible_id':self.manager['id'],'due':'overdue'})['items'][0]['id'],item['id'])
        self.assertEqual(self.api.listing(self.owner,{'priority':'low'})['items'],[])
        self.problem(400,self.api.listing,self.owner,{'priority':'invented'})
        self.foundation.save_contact(self.owner,req(revision=self.customer['revision'],name='Changed canonical customer'),self.customer['id'])
        self.problem(409,self.api.command,self.owner,item['id'],'transition',body)
        self.transition(item,'triaged')
        self.problem(409,self.api.save,self.owner,self.values(id=item['id'],revision=1,title='Stale edit'))

    def test_real_planning_conflicts_and_late_failure_roll_back_native_appointments(self):
        item=self.create();employee=self.api.planning.save_employee(self.owner,req(user_id=self.manager['id'],name='Synthetic assigned employee'))
        self.appointment(item,employee_ids=[employee['id']])
        self.problem(409,self.appointment,item,employee_ids=[employee['id']])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_appointments').fetchone()[0],1)
        original=self.api.event
        def fail(actor,item,kind,*args,**kwargs):
            if kind=='dispatched':raise RuntimeError('Synthetic failure after native appointment')
            return original(actor,item,kind,*args,**kwargs)
        with patch.object(self.api,'event',side_effect=fail):
            with self.assertRaises(RuntimeError):self.appointment(item,start_at='2026-11-05T09:00:00+01:00',end_at='2026-11-05T10:00:00+01:00',employee_ids=[employee['id']])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_appointments').fetchone()[0],1)
        self.assertEqual(len(self.api.view(self.owner,item['id'])['links']),1)

    def test_activity_correction_is_append_only_and_current_rights_gate_old_receipts(self):
        item=self.create();body=self.command_body(item,kind='call',text='Synthetic customer call',occurred_on='2026-11-03',supersedes_id=None,correction_reason='')
        recorded=self.api.command(self.manager,item['id'],'events',dict(body,source_sha256=self.api.view(self.manager,item['id'])['source_sha256']))
        corrected=self.command(item,'events',kind='call',text='Corrected documented words',occurred_on='2026-11-03',supersedes_id=recorded['event']['id'],correction_reason='Misheard wording')
        self.assertEqual(corrected['case']['revision'],item['revision'])
        self.assertEqual(len(self.api.history(self.owner,item['id'])['events']),3)
        self.office.assign(self.owner,self.project,self.manager['id'],remove=True)
        self.problem(404,self.api.view,self.manager,item['id'])
        self.assertEqual(self.api.listing(self.manager,{})['items'],[])

    def test_closed_cases_require_reopening_and_native_modules_do_not_disable_core_case(self):
        item=self.create();self.transition(item,'triaged');self.transition(item,'resolved');self.transition(item,'closed')
        self.problem(409,self.appointment,item)
        self.transition(item,'triaged')
        report=self.report()
        organization=Organization(self.office);state=organization.get(self.owner)
        state['modules']={key:dict(visible=value['visibility_override'],enabled=value['enabled']) for key,value in state['modules'].items()}
        state['modules']['planning']['enabled']=False;state['modules']['documents']['enabled']=False
        organization.save(self.owner,req(revision=state['revision'],needs=state['needs'],modules=state['modules']))
        self.problem(423,self.appointment,item)
        self.assertEqual(self.transition(item,'waiting_customer')['case']['status'],'waiting_customer')
        # The native signed source can still be read; creating the service link is paused.
        self.problem(423,self.api.command,self.owner,item['id'],'evidence',self.command_body(item,confirmation=True,report_id=report['id']))

    def test_immutable_guards_receipt_collision_and_integrity(self):
        item=self.create();self.appointment(item)
        body=self.command_body(item,kind='note',text='Original note',occurred_on='2026-11-03',supersedes_id=None,correction_reason='')
        result=self.api.command(self.owner,item['id'],'events',body)
        self.assertEqual(self.api.command(self.owner,item['id'],'events',body),result)
        error=self.problem(409,dispatch,self.office,self.owner,'/service/cases/'+item['id']+'/events','POST',dict(body,text='Changed nonce body'))
        self.assertIsNone(error.request_resolution)
        for table in protected_tables():
            with self.assertRaises(sqlite3.IntegrityError):self.office.db.execute('DELETE FROM '+table)
        validate_integrity(self.office)
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_service_requests_update_guard')
            changed=dict(result);changed['case']=dict(result['case'],status='closed')
            self.office.db.execute('UPDATE business_service_requests SET result_json=? WHERE request_id=?',(json.dumps(changed),body['request_id']))
        with self.assertRaises(ValueError):validate_integrity(self.office)


if __name__=='__main__':unittest.main()
