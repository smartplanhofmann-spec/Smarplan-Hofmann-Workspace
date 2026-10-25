"""Approved real time records become immutable, second-exact invoice sources."""
from datetime import datetime,timezone
import unittest
import uuid

from core import Problem
from business_planning import Planning,schema_statements as planning_schema
from business_time import TimeTracking,schema_statements as time_schema
from business_documents import render_prepared
from test_documents import DocumentsFixture


class TimeBillingTests(DocumentsFixture,unittest.TestCase):
    def setUp(self):
        super().setUp();self.settings()
        with self.office.db:
            for sql in planning_schema('BLOB')+time_schema('BLOB'):self.office.db.execute(sql)
        self.planning=Planning(self.office,clock=self.api.clock);self.time=TimeTracking(self.office,clock=self.api.clock)
        self.employee=self.planning.save_employee(self.owner,dict(request_id=uuid.uuid4().hex,user_id=self.owner['id'],name='Synthetic employee',weekly_minutes=2400,hourly_cost_minor=3500))
        self.entry=uuid.uuid4().hex
        base=dict(entry_id=self.entry,device_id='synthetic-clock',project_id=self.project)
        self.time.event(self.owner,dict(request_id=uuid.uuid4().hex,revision=0,sequence=1,action='start',occurred_at='2030-01-09T08:00:00+01:00',**base))
        self.time.event(self.owner,dict(request_id=uuid.uuid4().hex,revision=1,sequence=2,action='stop',occurred_at='2030-01-09T08:00:07+01:00',**base))

    def approve(self):
        day=self.time.summary(self.owner,dict(employee_id=self.employee['id'],**{'from':'2030-01-09','to':'2030-01-09'}))['days'][0]
        self.time.approve_day(self.owner,'2030-01-09',dict(request_id=uuid.uuid4().hex,employee_id=self.employee['id'],revision=day['revision']))

    def draft_time(self):return self.draft(kind='invoice',positions=[],time_entry_ids=[self.entry],hourly_rate_net='10000.00',time_tax_rate='19')

    def test_unapproved_rejected_then_second_exact_rate_and_double_billing_prevented(self):
        with self.assertRaises(Problem):self.draft_time()
        self.approve();draft=self.draft_time();position=draft['positions'][0]
        self.assertEqual('7',position['quantity']);self.assertEqual('SEC',position['unit']);self.assertEqual('3600',position['price_base_quantity'])
        self.assertEqual('19.44',position['net']);self.assertNotIn('hourly_cost',str(position))
        self.issue(draft)
        self.assertEqual([],self.api.time_sources(self.owner,self.project)['items'])
        with self.assertRaises(Problem):self.issue(self.draft_time())

    def test_later_approved_correction_invalidates_stale_render_before_number_is_consumed(self):
        self.approve();draft=self.draft_time();prepared=self.api.prepare_finalization(self.owner,draft['id'],1)
        self.time.correct_entry(self.owner,self.entry,dict(request_id=uuid.uuid4().hex,work_date='2030-01-09',delta_seconds=-1,reason='Synthetic corrected duration'))
        with self.assertRaises(Problem):self.api.finalize(self.owner,draft['id'],render_prepared(prepared),uuid.uuid4().hex)
        self.assertEqual(0,self.office.db.execute('SELECT count(*) FROM business_document_numbers').fetchone()[0])


if __name__=='__main__':unittest.main()
