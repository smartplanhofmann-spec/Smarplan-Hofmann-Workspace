"""Real SQLite bridge jobs: durable receipts, current epochs and restore safety."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import uuid

from cryptography.fernet import Fernet

from core import Office, Problem, canonical
from external_integrations import ExternalIntegrations
from integration_bridge import IntegrationBridgeJobs, validate_integrity, sanitize_after_restore


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='smartplan-bridge-')
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / 'office.db'
        self.office = Office(self.path)
        self.addCleanup(lambda: self.office.db.close())
        self.now = [10000.0]
        self.owner = self.actor('owner')
        self.project = self.office.add_project(self.owner, 'Synthetic bridge project', 'Synthetic customer')
        self.vault = Fernet(Fernet.generate_key())
        self.domain = ExternalIntegrations(self.office, clock=lambda:self.now[0])
        self.jobs = IntegrationBridgeJobs(self.office, clock=lambda:self.now[0])

    def actor(self, role):
        identifier = uuid.uuid4().hex
        email = identifier+'@example.test'
        with self.office.db:
            self.office.db.execute('INSERT INTO users(id,email,role,active) VALUES(?,?,?,1)',(identifier,email,role))
        return dict(id=identifier,email=email,role=role)

    def invoke(self, method, *args, **kwargs):
        with self.office.lock, self.office.db:
            return getattr(self.jobs,method)(*args,**kwargs)

    def domain_call(self, method, *args, **kwargs):
        with self.office.lock, self.office.db:
            return getattr(self.domain,method)(*args,**kwargs)

    def problem(self, status, callback):
        with self.assertRaises(Problem) as caught:
            callback()
        self.assertEqual(status,caught.exception.status,caught.exception.message)

    def cipher(self, payload='synthetic private configuration'):
        return self.vault.encrypt(payload.encode()).decode()

    def connect(self, provider='google_calendar', *, configured=False):
        values = dict(config=self.cipher(),expected_generation=0)
        if not configured:
            values.update(credential=self.cipher('synthetic account binding'),identity=dict(id='synthetic-account',label='Synthetic account'))
        return self.domain_call('put_connection',self.owner,provider,**values)

    def queue(self, *, provider='google_calendar',kind='catalog',generation=1,**kwargs):
        return self.invoke('queue',self.owner,provider,kind,generation=generation,**kwargs)

    def complete(self, job, *, payload=None,source_id='synthetic-delivery',generation=None,**kwargs):
        return self.invoke('complete',self.owner,job['provider'],job['id'],generation=generation or job['generation'],
                           payload={'items':[]} if payload is None else payload,source_id=source_id,**kwargs)

    def bind(self, provider='google_calendar', *, events=None):
        selection = (dict(calendar_id='calendar@example.test',event_ids=events or ['event-1'])
                     if provider=='google_calendar' else dict(folder_id='folder-1',drive_id='drive-1'))
        remote = selection['calendar_id'] if provider=='google_calendar' else selection['folder_id']
        result = self.domain_call('bind',self.owner,self.project,provider,remote,selection,
                                  generation=1,revision=0,request_id=uuid.uuid4().hex)
        return result,selection

    def snapshot(self, provider='google_calendar', *, selection=None):
        if selection is None:
            _,selection = self.bind(provider)
        resource = selection['calendar_id'] if provider=='google_calendar' else canonical(selection)
        return self.queue(provider=provider,kind='snapshot',resource=resource,project_id=self.project,revision=1,selection=selection)

    def test_pending_dedup_and_exact_receipt_survive_controller_restart(self):
        self.connect(configured=True)
        first = self.queue()
        duplicate = self.queue()
        self.assertEqual(first['id'],duplicate['id'])
        self.assertTrue(duplicate['duplicate'])
        self.office.db.close()
        self.office = Office(self.path)
        self.domain = ExternalIntegrations(self.office,clock=lambda:self.now[0])
        self.jobs = IntegrationBridgeJobs(self.office,clock=lambda:self.now[0])
        pending = self.invoke('pending',self.owner,'google_calendar',1)
        self.assertEqual([first['id']],[x['id'] for x in pending])
        completed = self.complete(first,payload={'items':[{'id':'calendar@example.test'}]})
        self.assertEqual('completed',completed['status'])
        self.assertEqual(completed['payload'],self.invoke('job',self.owner,'google_calendar',first['id'],generation=1)['payload'])
        self.assertTrue(self.complete(first,payload=completed['payload'])['duplicate'])
        validate_integrity(self.office)

    def test_first_catalogue_promotion_preserves_requested_epoch_and_retry(self):
        self.connect(configured=True)
        job = self.queue()
        with self.office.lock,self.office.db:
            connection = self.domain.put_connection(self.owner,'google_calendar',credential=self.cipher(),
                identity={'id':'confirmed-account','label':'Confirmed account'},expected_generation=1)
            result = self.jobs.complete(self.owner,'google_calendar',job['id'],generation=1,result_generation=connection['generation'],
                payload={'identity':{'id':'confirmed-account','label':'Confirmed account'},'items':[]},source_id='receipt-1')
        self.assertEqual((1,2),(result['requested_generation'],result['generation']))
        self.assertEqual(result['id'],self.invoke('latest',self.owner,'google_calendar','catalog',None,generation=2)['id'])
        self.assertTrue(self.complete(job,generation=1,result_generation=2,payload=result['payload'],source_id='receipt-1')['duplicate'])
        self.assertTrue(self.complete(job,generation=2,payload=result['payload'],source_id='receipt-1')['duplicate'])
        self.problem(409,lambda:self.invoke('job',self.owner,'google_calendar',job['id'],generation=1))
        validate_integrity(self.office)

    def test_promotion_cannot_cross_multiple_generations_or_promote_resource(self):
        self.connect()
        job = self.queue(kind='resource',resource='calendar@example.test')
        self.domain_call('put_connection',self.owner,'google_calendar',config=self.cipher('new config'),expected_generation=1)
        self.problem(409,lambda:self.complete(job,generation=1,result_generation=2))
        self.domain_call('put_connection',self.owner,'google_calendar',config=self.cipher('third config'),expected_generation=2)
        self.problem(409,lambda:self.complete(job,generation=1,result_generation=3))

    def test_onedrive_real_domain_folder_binding_queues_and_completes_snapshot(self):
        self.connect('onedrive')
        job = self.snapshot('onedrive')
        self.assertEqual({'drive_id':'drive-1','folder_id':'folder-1'},json.loads(job['resource']))
        payload = {'folder':{'id':'folder-1','drive_id':'drive-1','name':'Synthetic folder'},'files':[]}
        result = self.complete(job,payload=payload)
        self.assertEqual(payload,result['payload'])
        self.assertEqual(job['id'],self.invoke('latest',self.owner,'onedrive','snapshot',job['resource'],generation=1)['id'])
        validate_integrity(self.office)

    def test_snapshot_selection_is_canonical_and_exactly_bound_to_current_link(self):
        self.connect()
        _,selection = self.bind(events=['event-b','event-a'])
        first = self.snapshot(selection=selection)
        second = self.snapshot(selection=dict(calendar_id=selection['calendar_id'],event_ids=['event-a','event-b']))
        self.assertEqual(first['id'],second['id'])
        self.problem(409,lambda:self.snapshot(selection=dict(calendar_id=selection['calendar_id'],event_ids=['different-event'])))
        self.connect('onedrive')
        _,selection = self.bind('onedrive')
        self.problem(409,lambda:self.snapshot('onedrive',selection=dict(folder_id=selection['folder_id'],drive_id='different-drive')))

    def test_changed_unlinked_project_cannot_receive_or_reveal_old_job(self):
        self.connect()
        job = self.snapshot()
        self.domain_call('unlink',self.owner,self.project,'google_calendar',generation=1,revision=1,request_id=uuid.uuid4().hex)
        self.problem(409,lambda:self.complete(job))
        self.problem(409,lambda:self.invoke('job',self.owner,'google_calendar',job['id'],generation=1))
        self.assertEqual([],self.invoke('pending',self.owner,'google_calendar',1))
        self.assertEqual('expired',self.office.db.execute('SELECT status FROM external_bridge_jobs WHERE id=?',(job['id'],)).fetchone()[0])
        validate_integrity(self.office)

    def test_same_receipt_is_idempotent_changed_source_payload_or_error_conflicts(self):
        self.connect()
        job = self.queue()
        result = self.complete(job,payload={'items':[{'id':'one'}]})
        self.assertTrue(self.complete(job,payload=result['payload'])['duplicate'])
        self.problem(409,lambda:self.complete(job,payload=result['payload'],source_id='another-delivery'))
        self.problem(409,lambda:self.complete(job,payload={'items':[{'id':'two'}]}))
        self.problem(409,lambda:self.complete(job,payload=result['payload'],error_code='timeout'))
        self.assertEqual(result['payload'],self.invoke('job',self.owner,'google_calendar',job['id'],generation=1)['payload'])

    def test_delayed_older_resource_does_not_replace_newer_confirmed_request(self):
        second_project=self.office.add_project(self.owner,'Other synthetic project','Synthetic customer')
        for provider in ('google_calendar','onedrive'):
            with self.subTest(provider=provider):
                self.connect(provider)
                resource='calendar@example.test' if provider=='google_calendar' else canonical({'drive_id':'drive-1','folder_id':'folder-1'})
                older=self.queue(provider=provider,kind='resource',resource=resource,project_id=self.project)
                self.now[0]+=1
                newer=self.queue(provider=provider,kind='resource',resource=resource,project_id=second_project)
                self.now[0]+=1
                self.complete(newer,payload={'revision':'newer-request'})
                self.now[0]+=1
                self.complete(older,payload={'revision':'older-delayed-request'})
                latest=self.invoke('latest',self.owner,provider,'resource',resource,generation=1)
                self.assertEqual(newer['id'],latest['id'])
                self.assertEqual({'revision':'newer-request'},latest['payload'])
        validate_integrity(self.office)

    def test_old_catalogue_retry_cannot_replace_newer_confirmed_catalogue(self):
        self.connect()
        older=self.queue()
        self.complete(older,payload={'items':[{'id':'older-catalogue'}]})
        self.now[0]+=1
        newer=self.queue()
        self.now[0]+=1
        self.complete(newer,payload={'items':[{'id':'newer-catalogue'}]})
        self.now[0]+=1
        self.assertTrue(self.complete(older,payload={'items':[{'id':'older-catalogue'}]})['duplicate'])
        self.assertEqual(newer['id'],self.invoke('latest',self.owner,'google_calendar','catalog',None,generation=1)['id'])
        validate_integrity(self.office)

    def test_expired_job_is_not_delivered_or_returned_and_new_request_is_distinct(self):
        self.connect(configured=True)
        job = self.queue()
        self.now[0]+=3600
        self.problem(409,lambda:self.complete(job))
        self.assertEqual([],self.invoke('pending',self.owner,'google_calendar',1))
        replacement = self.queue()
        self.assertNotEqual(job['id'],replacement['id'])
        self.assertIsNone(self.invoke('latest',self.owner,'google_calendar','catalog',None,generation=1))
        validate_integrity(self.office)

    def test_clock_rollback_cannot_write_a_receipt_before_its_request(self):
        self.connect(configured=True)
        job = self.queue()
        self.now[0]-=1
        self.problem(409,lambda:self.complete(job))
        self.assertEqual('pending',self.invoke('job',self.owner,'google_calendar',job['id'],generation=1)['status'])
        validate_integrity(self.office)

    def test_two_hundred_pending_cap_fifty_result_bound_and_expired_history_preserved(self):
        self.connect()
        for i in range(200):
            self.queue(kind='resource',resource='calendar-'+str(i))
        self.assertEqual(50,len(self.invoke('pending',self.owner,'google_calendar',1)))
        self.problem(429,lambda:self.queue(kind='resource',resource='over-limit'))
        self.now[0]+=3600
        self.queue(kind='resource',resource='new-after-expiry')
        self.assertEqual(201,self.office.db.execute('SELECT COUNT(*) FROM external_bridge_jobs').fetchone()[0])
        self.assertEqual(1,len(self.invoke('pending',self.owner,'google_calendar',1)))

    def test_new_configuration_hides_old_jobs_without_blocking_new_generation(self):
        self.connect()
        old = self.queue()
        self.complete(old)
        old_pending = self.queue(kind='resource',resource='old-calendar')
        self.domain_call('put_connection',self.owner,'google_calendar',config=self.cipher('new configuration'),expected_generation=1)
        self.problem(409,lambda:self.invoke('job',self.owner,'google_calendar',old['id'],generation=1))
        self.assertIsNone(self.invoke('latest',self.owner,'google_calendar','catalog',None,generation=2))
        self.queue(generation=2)
        self.assertEqual('expired',self.office.db.execute('SELECT status FROM external_bridge_jobs WHERE id=?',(old_pending['id'],)).fetchone()[0])
        self.assertEqual(3,self.office.db.execute('SELECT COUNT(*) FROM external_bridge_jobs').fetchone()[0])
        validate_integrity(self.office)

    def test_fresh_actor_and_connection_owner_roles_are_checked_before_jobs(self):
        self.connect()
        job = self.queue()
        nonowner = self.actor('technician')
        nonowner['role']='owner'
        self.problem(403,lambda:self.invoke('pending',nonowner,'google_calendar',1))
        other_owner = self.actor('owner')
        self.office.db.execute("UPDATE users SET active=0 WHERE id=?",(self.owner['id'],));self.office.db.commit()
        self.problem(401,lambda:self.invoke('job',self.owner,'google_calendar',job['id'],generation=1))
        self.problem(409,lambda:self.invoke('touch',other_owner,'google_calendar','a'*64))
        self.assertEqual(0,self.office.db.execute('SELECT COUNT(*) FROM external_bridge_limits').fetchone()[0])

    def test_disconnect_or_provider_alias_cannot_expose_history(self):
        self.connect()
        job = self.queue()
        self.domain_call('disconnect',self.owner,'google_calendar',uuid.uuid4().hex,expected_generation=1)
        self.problem(409,lambda:self.invoke('pending',self.owner,'google_calendar',2))
        self.problem(409,lambda:self.complete(job))
        self.problem(400,lambda:self.queue(provider='dropbox'))

    def test_failed_receipt_uses_only_fixed_error_codes_and_never_latest_success(self):
        self.connect()
        job = self.queue()
        failed = self.complete(job,payload={},error_code='permission_denied')
        self.assertEqual('failed',failed['status'])
        self.assertTrue(self.complete(job,payload={},error_code='permission_denied')['duplicate'])
        self.assertIsNone(self.invoke('latest',self.owner,'google_calendar','catalog',None,generation=1))
        next_job = self.queue()
        self.problem(400,lambda:self.complete(next_job,error_code='arbitrary provider error text'))
        validate_integrity(self.office)

    def test_touch_commits_even_when_following_lookup_fails_and_resets_after_minute(self):
        self.connect()
        for _ in range(300):
            self.invoke('touch',self.owner,'google_calendar','b'*64)
        self.problem(404,lambda:self.invoke('job',self.owner,'google_calendar','f'*32,generation=1))
        self.problem(429,lambda:self.invoke('touch',self.owner,'google_calendar','b'*64))
        self.assertEqual(300,self.office.db.execute('SELECT request_count FROM external_bridge_limits').fetchone()[0])
        self.now[0]+=60
        self.assertEqual(299,self.invoke('touch',self.owner,'google_calendar','b'*64)['remaining'])
        validate_integrity(self.office)

    def test_payload_byte_item_depth_secret_and_source_bounds_are_enforced(self):
        self.connect()
        job = self.queue()
        for payload,status in [({'items':[{}]*1001},400),({'text':'ä'*(1024*1024)},413),({'refresh_token':'not-allowed'},400),({'v':float('nan')},400)]:
            self.problem(status,lambda:self.complete(job,payload=payload))
        nested = {}
        for _ in range(23):
            nested={'x':nested}
        self.problem(400,lambda:self.complete(job,payload=nested))
        self.problem(400,lambda:self.complete(job,source_id='x'*201))
        self.problem(400,lambda:self.complete(job,source_id='bad\nsource'))
        self.assertEqual('pending',self.invoke('job',self.owner,'google_calendar',job['id'],generation=1)['status'])

    def test_normal_sqlite_clone_preserves_rows_and_disaster_sanitize_only_clears_transients(self):
        self.connect()
        job = self.queue()
        self.complete(job)
        self.invoke('touch',self.owner,'google_calendar','c'*64)
        before_conn = tuple(self.office.db.execute('SELECT * FROM external_connections').fetchone())
        before_jobs = [tuple(row) for row in self.office.db.execute('SELECT * FROM external_bridge_jobs')]
        clone = Office(Path(self.temporary.name)/'clone.db')
        try:
            self.office.db.backup(clone.db)
            validate_integrity(clone)
            self.assertEqual(before_jobs,[tuple(row) for row in clone.db.execute('SELECT * FROM external_bridge_jobs')])
            with clone.lock,clone.db:
                sanitize_after_restore(clone)
            self.assertEqual(0,clone.db.execute('SELECT COUNT(*) FROM external_bridge_jobs').fetchone()[0])
            self.assertEqual(0,clone.db.execute('SELECT COUNT(*) FROM external_bridge_limits').fetchone()[0])
            self.assertEqual(before_conn,tuple(clone.db.execute('SELECT * FROM external_connections').fetchone()))
            validate_integrity(clone)
        finally:
            clone.db.close()

    def test_integrity_rejects_changed_payload_hash_and_request_fingerprint(self):
        self.connect()
        job = self.queue()
        self.complete(job,payload={'items':[{'id':'original'}]})
        with self.office.db:
            self.office.db.execute('UPDATE external_bridge_jobs SET payload_json=? WHERE id=?',(canonical({'items':[]}),job['id']))
        with self.assertRaises(ValueError):
            validate_integrity(self.office)
        with self.office.db:
            self.office.db.execute('UPDATE external_bridge_jobs SET payload_sha256=? WHERE id=?',(hashlib.sha256(canonical({'items':[]}).encode()).hexdigest(),job['id']))
        validate_integrity(self.office)
        with self.office.db:
            self.office.db.execute('UPDATE external_bridge_jobs SET request_hash=? WHERE id=?',('a'*64,job['id']))
        with self.assertRaises(ValueError):
            validate_integrity(self.office)

    def test_live_reads_reject_modified_result_and_integrity_rejects_future_epoch(self):
        self.connect()
        job = self.queue()
        self.complete(job,payload={'items':[{'id':'original'}]})
        with self.office.db:
            self.office.db.execute('UPDATE external_bridge_jobs SET payload_json=? WHERE id=?',(canonical({'items':[]}),job['id']))
        self.problem(409,lambda:self.invoke('job',self.owner,'google_calendar',job['id'],generation=1))
        with self.office.db:
            self.office.db.execute('UPDATE external_bridge_jobs SET payload_sha256=?,generation=2 WHERE id=?',
                (hashlib.sha256(canonical({'items':[]}).encode()).hexdigest(),job['id']))
        with self.assertRaises(ValueError):
            validate_integrity(self.office)
        with self.office.db:
            self.office.db.execute('UPDATE external_bridge_jobs SET generation=1 WHERE id=?',(job['id'],))
        validate_integrity(self.office)
        self.office.db.execute('PRAGMA foreign_keys=OFF')
        with self.office.db:
            self.office.db.execute('UPDATE external_bridge_jobs SET owner_id=? WHERE id=?',(uuid.uuid4().hex,job['id']))
        with self.assertRaises(ValueError):
            validate_integrity(self.office)


if __name__=='__main__':
    unittest.main()
