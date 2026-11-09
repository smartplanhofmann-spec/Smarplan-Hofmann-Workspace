"""Guarded real PostgreSQL runtime reads, independent readers and dump/restore."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import threading
import unittest
import uuid

import psycopg

import business_schema
from business_offline_binding import legacy_time_lookup
from core import Problem, canonical, digest
from online import release
from online import test_business_offline_binding_pg as base
from online.store import PostgresOffice
from online.test_postgres_accounting_components_integration import disposable_restore, evidence_for, approve


DSN = base.bound.fixture.fixture.DSN


@unittest.skipUnless(DSN, 'Own guarded disposable loopback PostgreSQL required')
class LegacyTimeRecoveryPostgres(unittest.TestCase):
    setUp = base.OfflineBindingPostgres.setUp
    reopen = base.OfflineBindingPostgres.reopen
    login = base.OfflineBindingPostgres.login
    call = base.OfflineBindingPostgres.call

    def workflow(self):
        project = self.office.add_project(self.owner, 'Synthetic retained time', 'Synthetic customer')
        employee = self.office.db.execute('SELECT * FROM business_employees WHERE user_id=?', (self.owner['id'],)).fetchone()
        if employee is None:
            employee = self.call('POST', '/business/employees', dict(request_id=uuid.uuid4().hex,
                user_id=self.owner['id'], name='Synthetic retained time owner', weekly_minutes=2400,
                hourly_cost_minor=3500), status=201).json
        at = (datetime.now(timezone.utc)-timedelta(days=1)).replace(hour=9,minute=0,second=0,microsecond=123000)
        start = dict(request_id=uuid.uuid4().hex,entry_id=uuid.uuid4().hex,device_id=uuid.uuid4().hex,
            sequence=1,revision=0,action='start',occurred_at=at.isoformat(),project_id=project)
        start['event_id']=start['request_id']
        first = self.call('POST','/business/time/events',start).json
        stop = dict(start,request_id=uuid.uuid4().hex,sequence=2,revision=1,action='stop',
            occurred_at=(at+timedelta(minutes=30)).replace(microsecond=456789).isoformat())
        stop['event_id']=stop['request_id']
        self.call('POST','/business/time/events',stop)
        core = dict(entry_id=stop['entry_id'],employee_id=first['entry']['employee_id'],project_id=project,
            category_id=first['entry']['category_id'],action='stop',occurred_at=stop['occurred_at'],
            device_id=stop['device_id'],sequence=2,revision=1)
        request = dict(schema_version=3,nonce=uuid.uuid4().hex,kind='time_event_core',project_id=project,
            entry_id=stop['entry_id'],request_id=stop['request_id'],request_hash=digest(canonical(core)))
        proof = self.call('POST','/business/offline/recovery/time-event',request).json
        self.assertEqual(proof['original']['core'],core)
        self.assertIs(type(proof['original']['core']['sequence']),int)
        self.assertIs(type(proof['original']['core']['revision']),int)
        self.assertTrue(business_schema.validate_integrity(self.office))
        return request,proof

    def test_actual_runtime_readers_do_not_consume_events_or_change_business_journals(self):
        request,proof=self.workflow()
        before=release.snapshot_fingerprint(DSN)
        barrier=threading.Barrier(2)
        def read(_):
            office=PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=5)
                return legacy_time_lookup(office,self.owner,request)
            finally:office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(list(pool.map(read,range(2))),[proof,proof])
        after=release.snapshot_fingerprint(DSN)
        for table in before:
            if table.startswith('business_') or table in ('projects','plan_versions','plan_requests'):
                self.assertEqual(after[table],before[table],table)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_approved_event_core_and_actual_dump_restore_preserve_same_original_proof(self):
        request,proof=self.workflow();employee=proof['original']['core']['employee_id'];day=proof['original']['core']['occurred_at'][:10]
        query='?employee_id='+employee+'&from='+day+'&to='+day
        current=self.call('GET','/business/time/accounts'+query).json
        self.call('POST','/business/time/days/'+day+'/approve',dict(request_id=uuid.uuid4().hex,
            employee_id=employee,revision=current['days'][0]['revision']))
        self.assertEqual(self.call('POST','/business/offline/recovery/time-event',request).json,proof)
        self.office.db.close()
        with disposable_restore(self.runtime) as (target,runtime,report):
            operator=PostgresOffice(target)
            try:approve(operator,evidence_for(operator,report))
            finally:operator.db.close()
            restored=PostgresOffice(runtime)
            try:
                self.assertEqual(legacy_time_lookup(restored,self.owner,request),proof)
                self.assertEqual(restored.db.execute('SELECT COUNT(*) FROM business_time_events WHERE entry_id=?',
                    (request['entry_id'],)).fetchone()[0],2)
                self.assertEqual(restored.db.execute('SELECT COUNT(*) FROM plan_sessions').fetchone()[0],0)
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:restored.db.close()

    def test_changed_record_and_missing_original_never_receive_nonacceptance_authority(self):
        request,proof=self.workflow()
        with psycopg.connect(DSN) as operator:
            operator.execute('UPDATE business_time_events SET device_id=%s WHERE request_id=%s',
                ('synthetic-corrupt-archive',request['request_id']))
        for value in (request,dict(request,request_id=uuid.uuid4().hex)):
            with self.assertRaises(Problem) as error:legacy_time_lookup(self.office,self.owner,value)
            self.assertIn(error.exception.status,(404,409))
            self.assertIsNone(getattr(error.exception,'request_resolution',None))
