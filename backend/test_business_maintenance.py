"""Synthetic maintenance anniversaries, retry-safe visits and frozen service history."""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import tempfile
import unittest
import uuid

from core import Office, Problem
from business_maintenance import BusinessMaintenance, schema_statements, validate_integrity
from business_operations import BusinessOperations, schema_statements as operation_schema


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.office=Office(Path(self.temp.name)/'office.db'); self.addCleanup(self.office.db.close)
        from business_foundation import schema_statements as foundation_schema
        for statement in foundation_schema('BLOB')+operation_schema('BLOB')+schema_statements('BLOB'): self.office.db.execute(statement)
        self.office.db.commit()
        self.owner=self.actor('owner'); self.tech=self.actor('technician')
        self.project=self.office.add_project(self.owner,'Synthetic maintenance','Synthetic customer')
        self.other=self.office.add_project(self.owner,'Other customer site','Other customer')
        self.office.assign(self.owner,self.project,self.tech['id'])
        self.api=BusinessMaintenance(self.office,clock=lambda:datetime(2028,3,1,10,tzinfo=timezone.utc))
        self.ops=BusinessOperations(self.office,clock=lambda:datetime(2028,3,1,10,tzinfo=timezone.utc))
        self.asset=self.api.save_asset(self.tech,self.project,self.req(name='Synthetic heat pump',serial_number='SYN-123',location='Technical room'))

    def actor(self,role):
        email=uuid.uuid4().hex+'@example.test'; return dict(id=self.office.add_user(email,'Synthetic-password-123',role),role=role,email=email)

    def req(self,**data): return dict(request_id=uuid.uuid4().hex,**data)

    def error(self,status,function,*args):
        with self.assertRaises(Problem) as caught: function(*args)
        self.assertEqual(caught.exception.status,status,caught.exception.message)

    def contract(self,**extra):
        return self.api.save_contract(self.owner,self.project,self.req(asset_id=self.asset['id'],title='Synthetic monthly service',anchor_date='2028-01-31',interval_unit='months',interval_count=1,**extra))

    def test_month_end_leap_year_and_repeated_scheduling_do_not_drift_or_duplicate(self):
        contract=self.contract()
        body=self.req(as_of='2028-03-31',project_id=self.project)
        scheduled=self.api.schedule_due(self.owner,body)
        self.assertEqual([visit['due_date'] for visit in scheduled['items']],['2028-01-31','2028-02-29','2028-03-31'])
        self.assertEqual(self.api.schedule_due(self.owner,body),scheduled)
        again=self.api.schedule_due(self.owner,self.req(as_of='2028-03-31',project_id=self.project))
        self.assertEqual(again['items'],[])
        history=self.api.history(self.tech,self.project,asset_id=self.asset['id'])
        self.assertEqual(len(history),3)
        self.assertTrue(all(item['contract_snapshot']['revision']==contract['revision'] for item in history))
        self.assertEqual(self.api.list_contracts(self.owner,self.project)[0]['next_due_date'],'2028-04-30')
        self.assertTrue(validate_integrity(self.office))

    def test_annual_anchor_leap_day_returns_to_feb29_in_leap_year(self):
        self.api.save_contract(self.owner,self.project,self.req(asset_id=self.asset['id'],title='Annual',anchor_date='2024-02-29',interval_unit='months',interval_count=12))
        scheduled=self.api.schedule_due(self.owner,self.req(as_of='2028-02-29',project_id=self.project))
        self.assertEqual([item['due_date'] for item in scheduled['items']],['2024-02-29','2025-02-28','2026-02-28','2027-02-28','2028-02-29'])

    def test_visit_requires_signed_same_project_service_and_keeps_frozen_pdf_hash(self):
        self.contract()
        visit=self.api.schedule_due(self.owner,self.req(as_of='2028-01-31',project_id=self.project))['items'][0]
        draft=self.ops.save_entry(self.tech,self.project,'service',self.req(title='Synthetic service',description='Filter checked'))
        self.error(409,self.api.complete_visit,self.tech,self.project,visit['id'],self.req(revision=1,report_id=draft['id']))
        signed=self.ops.sign_entry(self.tech,self.project,draft['id'],self.req(revision=1,expected_hash=draft['content_hash'],signer='Synthetic customer',strokes=[[[0.1,0.2],[0.8,0.5]]]))
        body=self.req(revision=1,report_id=signed['id'])
        completed=self.api.complete_visit(self.tech,self.project,visit['id'],body)
        self.assertEqual(self.api.complete_visit(self.tech,self.project,visit['id'],body),completed)
        self.assertEqual(completed['status'],'completed')
        self.assertEqual(completed['report_pdf_sha256'],hashlib.sha256(self.ops.entry_pdf(self.tech,self.project,signed['id'])).hexdigest())
        self.api.save_asset(self.tech,self.project,self.req(revision=1,name='Renamed after visit'),self.asset['id'])
        self.assertEqual(self.api.history(self.tech,self.project)[0]['asset_snapshot']['name'],'Synthetic heat pump')
        self.error(404,self.api.complete_visit,self.owner,self.other,visit['id'],self.req(revision=1,report_id=signed['id']))
        self.assertTrue(validate_integrity(self.office))

    def test_paused_contract_and_revoked_project_do_not_create_visits(self):
        contract=self.contract(active=False)
        self.assertEqual(self.api.schedule_due(self.owner,self.req(as_of='2028-03-01',project_id=self.project))['items'],[])
        self.office.assign(self.owner,self.project,self.tech['id'],remove=True)
        self.error(404,self.api.list_assets,self.tech,self.project)
        self.error(404,self.api.save_asset,self.tech,self.project,self.req(name='Forbidden'))

if __name__=='__main__': unittest.main()
