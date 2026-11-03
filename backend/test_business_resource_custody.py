"""Actual canonical calendar/custody evidence; no inspection is inferred."""
import base64
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import uuid

from core import Office,Problem
from business_foundation import BusinessFoundation
from business_organization import Organization
from business_resource_custody import ResourceCustody,HANDOFF_FIELDS,RETURN_FIELDS,validate_integrity,protected_tables,dispatch
from business_service import Service


def req(**values):return dict(request_id=uuid.uuid4().hex,**values)


class ResourceCustodyTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='synthetic-resource-custody-');self.addCleanup(temporary.cleanup)
        self.office=Office(Path(temporary.name)/'office.db');self.addCleanup(self.office.db.close)
        self.owner=dict(id=self.office.add_user('custody-owner@example.test','Synthetic-resource-owner-password','owner'),role='owner')
        self.manager=dict(id=self.office.add_user('custody-manager@example.test','Synthetic-resource-manager-password','manager'),role='manager')
        self.api=ResourceCustody(self.office,clock=lambda:datetime(2026,11,3,12,tzinfo=timezone.utc));self.planning=self.api.planning
        self.resource=self.planning.save_resource(self.owner,req(name='Synthetic test drill',kind='tool',code='SYN-DRILL'))
        self.employee=self.planning.save_employee(self.owner,req(user_id=self.manager['id'],name='Synthetic actual employee'))
        self.customer=BusinessFoundation(self.office).save_contact(self.owner,req(name='Synthetic equipment customer'))
        self.project=self.office.add_project(self.owner,'Synthetic equipment project',customer_id=self.customer['id']);self.office.assign(self.owner,self.project,self.manager['id'])
    def problem(self,status,fn,*args,**kwargs):
        with self.assertRaises(Problem) as caught:fn(*args,**kwargs)
        self.assertEqual(caught.exception.status,status,caught.exception.message);return caught.exception
    def view(self):return self.api.view(self.owner,self.resource['id'])
    def body(self,**values):return req(source_sha256=self.view()['source_sha256'],confirmation=True,**values)
    def command(self,action,**values):return self.api.command(self.owner,self.resource['id'],action,self.body(**values))
    def profile_values(self,**changes):
        current=self.view();values={k:current['profile'][k] for k in ('revision','serial_number','manufacturer','model','location','notes')}
        values.update(condition=current['state']['condition'],reason='Synthetic explicitly reviewed profile');values.update(changes);return values
    def profile(self,**changes):return self.command('profile',**self.profile_values(**changes))
    def requirement(self,**changes):
        values=dict(revision=0,title='Synthetic mandatory operator requirement',due_on='2026-11-01',required_for_use=True,active=True,notes='Actual documented requirement',reason='Explicitly required for safe use');values.update(changes)
        return self.command('requirements',**values)['record']
    def file(self,name='actual-proof.pdf'):
        raw=b'%PDF-1.7\nSynthetic original inspection evidence\n%%EOF'
        return self.api.upload(self.owner,self.resource['id'],req(filename=name,media_type='application/pdf',content_base64=base64.b64encode(raw).decode()))
    def inspect(self,requirement,evidence,**changes):
        values=dict(requirement_id=requirement['id'],requirement_revision=requirement['revision'],performed_at='2026-11-02T09:00:00Z',inspector='Synthetic named inspector',result='passed',next_due_on='2026-11-04',evidence_id=evidence['id'],note='Actual test recorded in attached original',supersedes_id=None,correction_reason='');values.update(changes)
        return self.command('inspections',**values)['record']
    def handoff_values(self,**changes):
        values=dict(employee_id=self.employee['id'],project_id=self.project,issued_at='2026-11-03T09:00:00Z',expected_return_at='2026-11-03T10:00:00Z',condition='serviceable',notes='Actual issue acknowledged',evidence_id=None);values.update(changes);return values
    def handoff(self,**changes):return self.command('handoffs',**self.handoff_values(**changes))
    def returned(self,handoff,**changes):
        values=dict(handoff_id=handoff['id'],returned_at='2026-11-03T11:00:00Z',received_by_employee_id=self.employee['id'],condition='serviceable',notes='Actual return examined',evidence_id=None);values.update(changes)
        return self.command('returns',**values)
    def appointment_values(self,**changes):
        values=dict(title='Synthetic actual equipment appointment',start_at='2026-11-04T09:00:00+01:00',end_at='2026-11-04T10:00:00+01:00',timezone='Europe/Berlin',resource_ids=[self.resource['id']],employee_ids=[self.employee['id']]);values.update(changes);return req(**values)
    def appointment(self,**changes):return self.planning.save_appointment(self.owner,self.project,self.appointment_values(**changes))
    def availability(self,**changes):
        values=dict(start_at='2026-11-04T09:00:00+01:00',end_at='2026-11-04T10:00:00+01:00',timezone='Europe/Berlin',employee_id=self.employee['id'],project_id=self.project);values.update(changes)
        return self.api.availability(self.owner,self.resource['id'],values)

    def test_legacy_resource_is_readable_without_fabricated_inspection_and_calendar_is_current(self):
        item=self.view();self.assertFalse(item['state']['configured']);self.assertEqual(item['state']['inspection_knowledge'],'unconfigured');self.assertEqual(item['state']['condition'],'unknown')
        self.assertTrue(self.availability()['available']);before=item['source_sha256']
        booking=self.appointment(start_at='2026-11-03T12:00:00Z',end_at='2026-11-03T13:00:00Z')
        after=self.view();self.assertNotEqual(before,after['source_sha256']);self.assertFalse(after['state']['available']);self.assertEqual(after['state']['blockers'][0]['code'],'reservation')
        self.assertEqual(self.planning.resources(self.owner)['items'][0]['id'],item['id'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_resource_inspections').fetchone()[0],0)

    def test_required_evidence_dates_identity_and_safety_holds_cannot_be_overridden(self):
        self.profile(serial_number='SYN-001');requirement=self.requirement();evidence=self.file()
        self.problem(409,self.appointment,override_conflicts=True,override_reason='Must not bypass actual inspection')
        self.problem(400,self.inspect,requirement,evidence,performed_at='2026-11-04T10:00:00Z')
        self.problem(400,self.inspect,requirement,evidence,evidence_id=None)
        self.inspect(requirement,evidence)
        self.assertTrue(self.availability()['available'])
        self.problem(409,self.appointment,start_at='2026-11-05T09:00:00Z',end_at='2026-11-05T10:00:00Z',override_conflicts=True,override_reason='No date bypass')
        self.problem(409,self.appointment,start_at='2026-11-01T09:00:00Z',end_at='2026-11-01T10:00:00Z')
        self.profile(serial_number='SYN-002')
        self.problem(409,self.appointment)
        self.inspect(requirement,evidence,performed_at='2026-11-03T09:00:00Z')
        self.appointment();validate_integrity(self.office)

    def test_service_dispatch_reuses_actual_resource_gate_and_cancel_is_possible(self):
        api=Service(self.office)
        case=api.save(self.owner,req(revision=0,customer_id=self.customer['id'],person_id=None,project_id=self.project,asset_id=None,contract_id=None,visit_id=None,inquiry_id=None,defect_id=None,title='Synthetic service request',kind='request',priority='normal',responsible_id=self.owner['id'],follow_up_on=None,description='Synthetic service needs actual drill'))
        def dispatch_service():
            current=api.view(self.owner,case['id']);values=self.appointment_values();values.pop('request_id')
            return api.command(self.owner,case['id'],'dispatch',req(revision=current['revision'],source_sha256=current['source_sha256'],confirmation=True,details='',**values))
        self.profile(condition='out_of_service');self.problem(409,dispatch_service)
        self.profile(condition='serviceable');result=dispatch_service();appointment=result['link']['source_snapshot']
        self.profile(condition='restricted');self.resource=self.planning.save_resource(self.owner,req(id=self.resource['id'],revision=self.resource['revision'],active=False))
        cancelled=self.planning.save_appointment(self.owner,self.project,req(id=appointment['id'],revision=appointment['revision'],status='cancelled'))
        self.assertEqual(cancelled['status'],'cancelled');validate_integrity(self.office)

    def test_actual_issue_return_correct_identity_and_expected_return_is_not_actual_return(self):
        body=self.body(**self.handoff_values());issued=self.api.command(self.owner,self.resource['id'],'handoffs',body)
        self.assertEqual(self.api.command(self.owner,self.resource['id'],'handoffs',body),issued)
        self.problem(409,self.handoff)
        self.assertTrue(self.availability()['available']);self.assertFalse(self.availability(employee_id=None)['available'])
        self.problem(409,self.appointment,employee_ids=[])
        self.problem(409,self.profile,serial_number='Cannot silently exchange issued drill')
        self.problem(409,self.planning.save_resource,self.owner,req(id=self.resource['id'],revision=self.resource['revision'],code='CHANGED'))
        self.problem(409,self.returned,issued['record'],returned_at='2026-11-03T08:00:00Z')
        self.returned(issued['record'],condition='out_of_service');self.assertFalse(self.availability()['available'])
        self.profile(location='Quarantined tool shelf');self.assertEqual(self.view()['state']['condition'],'out_of_service')
        self.profile(condition='serviceable',reason='Actual repair and explicit release reviewed');self.assertTrue(self.availability()['available'])
        self.assertEqual(self.api.command(self.owner,self.resource['id'],'handoffs',body),issued)
        validate_integrity(self.office)

    def test_corrections_preserve_originals_enforce_evidence_and_actual_intervals(self):
        issued=self.handoff()['record'];returned=self.returned(issued,condition='restricted')['record'];evidence=self.file()
        values={k:returned[k] for k in RETURN_FIELDS};values.update(condition='serviceable',notes='Corrected original transcription')
        self.problem(400,self.command,'corrections',target_kind='return',target_id=returned['id'],values=values,reason='Transcription corrected with original',evidence_id=None)
        corrected=self.command('corrections',target_kind='return',target_id=returned['id'],values=values,reason='Transcription corrected with original',evidence_id=evidence['id'])
        self.assertEqual(corrected['resource']['state']['condition'],'serviceable')
        second=self.handoff(issued_at='2026-11-03T11:30:00Z',expected_return_at=None,condition='out_of_service')['record']
        self.command('corrections',target_kind='return',target_id=returned['id'],values=values,reason='Second correction to earlier cycle',evidence_id=evidence['id'])
        self.assertEqual(self.view()['state']['condition'],'out_of_service')
        values['returned_at']='2026-11-03T11:45:00Z';self.problem(409,self.command,'corrections',target_kind='return',target_id=returned['id'],values=values,reason='Would overlap second actual issue',evidence_id=evidence['id'])
        history=self.api.history(self.owner,self.resource['id']);self.assertEqual(history['returns'][0],returned);self.assertEqual(len(history['corrections']),2)
        self.assertEqual(self.view()['state']['open_handoff']['id'],second['id']);validate_integrity(self.office)

    def test_failed_inspection_correction_and_requirement_deactivation_remain_explicit(self):
        requirement=self.requirement();evidence=self.file();failed=self.inspect(requirement,evidence,result='failed')
        self.problem(409,self.appointment)
        corrected=self.inspect(requirement,evidence,supersedes_id=failed['id'],correction_reason='Actual original proves recording error')
        self.assertTrue(self.availability()['available']);self.assertEqual(self.view()['inspections'][0]['result'],'failed')
        self.problem(409,self.inspect,requirement,evidence,supersedes_id=failed['id'],correction_reason='Old superseded original')
        changed=self.requirement(id=requirement['id'],revision=1,notes='Changed exact requirement')
        self.problem(409,self.appointment);self.problem(409,self.inspect,requirement,evidence)
        self.requirement(id=requirement['id'],revision=2,required_for_use=False,reason='Explicit reviewed informational requirement')
        self.assertTrue(self.availability()['available']);validate_integrity(self.office)

    def test_source_changes_late_rollback_exact_receipt_and_current_permissions(self):
        body=self.body(**self.profile_values(serial_number='SYN-ROLLBACK'));self.appointment()
        error=self.problem(409,dispatch,self.office,self.owner,'/resource-custody/'+self.resource['id']+'/profile','POST',body);self.assertEqual(error.request_resolution,'not_accepted')
        body=self.body(**self.profile_values(serial_number='SYN-ROLLBACK'))
        with patch.object(self.office,'audit',side_effect=RuntimeError('Synthetic late audit failure')):
            with self.assertRaises(RuntimeError):self.api.command(self.owner,self.resource['id'],'profile',body)
        self.assertEqual(self.view()['profile']['revision'],0)
        result=self.api.command(self.owner,self.resource['id'],'profile',body)
        error=self.problem(409,dispatch,self.office,self.owner,'/resource-custody/'+self.resource['id']+'/profile','POST',dict(body,serial_number='Different same nonce'))
        self.assertIsNone(error.request_resolution)
        organization=Organization(self.office);state=organization.get(self.owner);modules={k:dict(visible=v['visibility_override'],enabled=v['enabled']) for k,v in state['modules'].items()};modules['planning']['enabled']=False
        organization.save(self.owner,req(revision=state['revision'],needs=state['needs'],modules=modules))
        self.assertEqual(self.api.command(self.owner,self.resource['id'],'profile',body),result);self.problem(423,self.profile,location='New action while paused')
        with self.office.db:self.office.db.execute("UPDATE users SET role='technician' WHERE id=?",(self.owner['id'],))
        self.problem(403,self.api.command,self.owner,self.resource['id'],'profile',body)
        self.problem(403,self.api.view,self.owner,self.resource['id'])

    def test_evidence_and_history_guards_integrity_and_safe_employee_dto(self):
        requirement=self.requirement();evidence=self.file();self.inspect(requirement,evidence);issued=self.handoff()['record'];self.returned(issued)
        for employee in self.api.options(self.owner)['employees']:self.assertNotIn('hourly_cost_minor',employee)
        for table in protected_tables():
            if self.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0]:
                with self.assertRaises(sqlite3.IntegrityError):self.office.db.execute('DELETE FROM '+table)
        validate_integrity(self.office)
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_resource_evidence_update_guard')
            self.office.db.execute('UPDATE business_resource_evidence SET content=? WHERE id=?',(b'%PDF-corrupt',evidence['id']))
        self.problem(409,self.availability)
        with self.assertRaises(ValueError):validate_integrity(self.office)


if __name__=='__main__':unittest.main()
