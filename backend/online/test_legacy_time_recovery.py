"""Hash-only time event reconciliation using actual MFA and old event hashes."""
from datetime import datetime, timedelta, timezone
import json
import os
import unittest
import uuid

from core import canonical, digest
from online import test_offline_instance_binding as fixture


PATH = '/business/offline/recovery/time-event'


class LegacyTimeRecoveryHttpTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.OfflineInstanceBindingHttpTests('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.company = self.f.a
        self.actor = self.f.account
        self.token = self.company['token']
        self.employee = self.employee_for(self.company, self.actor)
        instant = (datetime.now(timezone.utc) - timedelta(days=1)).replace(hour=9, minute=0, second=0, microsecond=123000)
        self.start = dict(request_id=uuid.uuid4().hex, entry_id=uuid.uuid4().hex, device_id=uuid.uuid4().hex,
            sequence=1, revision=0, action='start', occurred_at=instant.strftime('%Y-%m-%dT%H:%M:%S.123Z'), project_id=self.f.project)
        self.start['event_id'] = self.start['request_id']
        self.first = self.call('/business/time/events', self.start).json
        self.stop = dict(self.start, request_id=uuid.uuid4().hex, sequence=2, revision=1, action='stop',
            occurred_at=(instant + timedelta(minutes=30)).strftime('%Y-%m-%dT%H:%M:%S.456789Z'))
        self.stop['event_id'] = self.stop['request_id']
        self.accepted = self.call('/business/time/events', self.stop).json
        self.core = dict(entry_id=self.stop['entry_id'], employee_id=self.first['entry']['employee_id'],
            project_id=self.f.project, category_id=self.first['entry']['category_id'],
            action='stop', occurred_at=datetime.fromisoformat(self.stop['occurred_at']).isoformat(),
            device_id=self.stop['device_id'], sequence=2, revision=1)
        self.request = dict(schema_version=3, nonce=uuid.uuid4().hex, kind='time_event_core', project_id=self.f.project,
            entry_id=self.stop['entry_id'], request_id=self.stop['request_id'], request_hash=digest(canonical(self.core)))

    def employee_for(self, company, user):
        return self.f.call(company, '/business/employees', dict(request_id=uuid.uuid4().hex, user_id=user,
            name='Synthetic retained employee', weekly_minutes=2400, hourly_cost_minor=3500), status=201).json

    def call(self, path, body=None, *, status=200, **kw):
        return self.f.call(self.company, path, body, token=self.token, status=status, **kw)

    def test_actual_old_core_hash_matches_without_replaying_event_or_replacing_current_timer(self):
        before = list(self.company['office'].db.execute('SELECT * FROM business_time_events'))
        reply = self.call(PATH, self.request)
        value = reply.json
        self.assertEqual(set(value), {'schema_version','nonce','lookup_hash','binding','kind','project_id','entry_id','request_id','request_hash','original'})
        self.assertEqual(value['schema_version'], 3)
        self.assertEqual(value['lookup_hash'], digest(canonical(self.request)))
        self.assertEqual(value['nonce'], self.request['nonce'])
        self.assertEqual(value['binding']['instance_id'], self.company['instance_id'])
        original = value['original']
        self.assertEqual(original['core'], self.core)
        self.assertEqual(original['actor_id'], self.actor)
        self.assertEqual(original['event_id'], self.stop['request_id'])
        self.assertEqual(original['request_hash'], self.request['request_hash'])
        for excluded in ('position','latitude','longitude','hourly_cost_minor','worked_seconds','entry','status','approved_work_dates'):
            self.assertNotIn(excluded, original)
        self.assertIn('no-store', reply.headers['Cache-Control'])
        self.assertEqual(list(self.company['office'].db.execute('SELECT * FROM business_time_events')), before)
        self.assertEqual(self.call('/business/time/entries/'+self.stop['entry_id']).json, self.accepted['entry'])

    def test_same_account_project_event_and_request_in_replacement_firm_need_old_employee_basis(self):
        b = self.f.b
        self.employee_for(b, self.f.account)
        self.f.call(b, '/business/time/events', self.start)
        self.f.call(b, '/business/time/events', self.stop)
        reply = self.f.call(b, PATH, self.request, status=409)
        self.assertNotIn('original', reply.json)
        self.assertNotIn('request_resolution', reply.json)
        for company in (self.company, b):
            self.assertEqual(company['office'].db.execute('SELECT COUNT(*) FROM business_time_events').fetchone()[0], 2)

    def test_readonly_mode_keeps_core_proof_and_feature_without_releasing_event_writes(self):
        from business_schema import set_mode
        caps = self.call('/business/capabilities').json
        self.assertIn('offline_time_event_recovery', caps['features'])
        before = self.call(PATH, self.request).json
        set_mode(self.company['office'], 'legacy')
        self.assertEqual(self.call(PATH, self.request).json, before)
        self.call('/business/time/events', self.stop, status=409)

    def test_approved_day_and_location_erasure_do_not_replace_original_core_with_current_entry(self):
        before = self.call(PATH, self.request).json
        day = self.core['occurred_at'][:10]
        query = '?employee_id='+self.employee['id']+'&from='+day+'&to='+day
        summary = self.call('/business/time/accounts'+query).json
        self.call('/business/time/days/'+day+'/approve', dict(request_id=uuid.uuid4().hex,
            employee_id=self.employee['id'], revision=summary['days'][0]['revision']))
        self.assertEqual(self.call('/business/time/entries/'+self.stop['entry_id']).json['status'], 'approved')
        self.assertEqual(self.call(PATH, self.request).json, before)
        row = self.company['office'].db.execute('SELECT location_redacted_at FROM business_time_events WHERE request_id=?',
            (self.stop['request_id'],)).fetchone()
        self.assertIsNotNone(row['location_redacted_at'])

    def test_absent_and_wrong_original_hash_are_never_nonacceptance(self):
        for changes, status in ((dict(request_id=uuid.uuid4().hex),404), (dict(request_hash='f'*64),409),
                                (dict(entry_id=uuid.uuid4().hex),409)):
            reply = self.call(PATH, dict(self.request, **changes), status=status)
            self.assertNotIn('original', reply.json)
            self.assertNotIn('request_resolution', reply.json)

    def test_altered_record_cannot_be_returned_as_original_even_with_same_stored_hash(self):
        office = self.company['office']
        with office.db:
            office.db.execute('UPDATE business_time_events SET device_id=? WHERE request_id=?', ('changed-device', self.stop['request_id']))
        self.call(PATH, self.request, status=409)

    def test_actual_mfa_own_employee_and_fresh_project_assignment_are_required(self):
        office = self.company['office']
        user = office.add_user('retained-worker@example.test', fixture.PASSWORD, 'technician')
        self.f.call(self.company, '/assignments', dict(project_id=self.f.project, user_id=user))
        self.employee_for(self.company, user)
        token = self.f.login(self.company, 'retained-worker@example.test')
        self.f.call(self.company, PATH, self.request, token=token, status=404)
        body = dict(self.start, request_id=uuid.uuid4().hex, entry_id=uuid.uuid4().hex)
        body['event_id'] = body['request_id']
        result = self.f.call(self.company, '/business/time/events', body, token=token).json
        core = dict(self.core, entry_id=body['entry_id'], employee_id=result['entry']['employee_id'],
            action='start', occurred_at=datetime.fromisoformat(body['occurred_at']).isoformat(), sequence=1, revision=0)
        request = dict(self.request, entry_id=body['entry_id'], request_id=body['request_id'], request_hash=digest(canonical(core)))
        self.f.call(self.company, PATH, request, token=token)
        self.f.call(self.company, '/assignments', dict(project_id=self.f.project, user_id=user, remove=True))
        self.f.call(self.company, PATH, request, token=token, status=404)

    def test_inactive_identity_and_real_bound_device_tokens_do_not_receive_original(self):
        for route in ('/offline/access/v2', '/business/offline/access/v2'):
            grant = self.call(route, {}, status=201).json
            self.f.call(self.company, PATH, self.request, token=grant['token'],
                headers={'X-Smartplan-Offline-Binding':self.company['instance_id']+':'+self.actor}, status=403)
        with self.company['office'].db:
            self.company['office'].db.execute('UPDATE users SET active=0 WHERE id=?', (self.actor,))
        self.call(PATH, self.request, status=401)

    def test_strict_metadata_query_media_method_duplicate_and_raw_size(self):
        for changes in (dict(schema_version=True), dict(kind='plan_write'), dict(body=self.stop), dict(employee_id=self.employee['id'])):
            self.call(PATH, dict(self.request, **changes), status=400)
        self.call(PATH+'?project_id='+self.f.project, self.request, status=400)
        self.call(PATH, status=405)
        raw=json.dumps(self.request).encode();duplicated=raw[:-1]+b',"schema_version":3}'
        response=self.company['client'].post('/api/v1'+PATH,base_url='https://same.example.test',
            headers={'Authorization':'Bearer '+self.token},data=duplicated,content_type='application/json')
        self.assertEqual(response.status_code,400)
        response=self.company['client'].post('/api/v1'+PATH,base_url='https://same.example.test',
            headers={'Authorization':'Bearer '+self.token},data=raw+b' '*4096,content_type='application/json')
        self.assertEqual(response.status_code,413)


@unittest.skipUnless(os.name == 'posix', 'Private local runtime storage requires POSIX')
class LegacyTimeRecoveryLocalHttpTests(unittest.TestCase):
    """Exercise the packaged local HTTP handler, including its raw body limit."""

    def setUp(self):
        self.f = fixture.OfflineInstanceBindingLocalHttpTests('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.f.call('/business/employees', dict(request_id=uuid.uuid4().hex,
            user_id=self.f.account, name='Synthetic local employee',
            weekly_minutes=2400, hourly_cost_minor=3500), status=201)
        instant = (datetime.now(timezone.utc) - timedelta(days=1)).replace(microsecond=0)
        body = dict(request_id=uuid.uuid4().hex, entry_id=uuid.uuid4().hex,
            device_id=uuid.uuid4().hex, sequence=1, revision=0, action='start',
            occurred_at=instant.isoformat(), project_id=self.f.project)
        body['event_id'] = body['request_id']
        original = self.f.call('/business/time/events', body)
        core = dict(entry_id=body['entry_id'], employee_id=original['entry']['employee_id'],
            project_id=self.f.project, category_id=original['entry']['category_id'],
            action='start', occurred_at=instant.isoformat(), device_id=body['device_id'],
            sequence=1, revision=0)
        self.query = dict(schema_version=3, nonce=uuid.uuid4().hex, kind='time_event_core',
            project_id=self.f.project, entry_id=body['entry_id'],
            request_id=body['request_id'], request_hash=digest(canonical(core)))
        self.core = core

    def test_local_original_is_read_only_and_preserves_existing_time_event(self):
        before = list(self.f.office.db.execute('SELECT * FROM business_time_events'))
        reply = self.f.call(PATH, self.query)
        self.assertEqual(reply['original']['core'], self.core)
        self.assertEqual(reply['lookup_hash'], digest(canonical(self.query)))
        self.assertEqual(reply['binding']['instance_id'], self.f.instance)
        self.assertEqual(list(self.f.office.db.execute('SELECT * FROM business_time_events')), before)

    def test_local_framing_limit_ambiguity_and_device_scope_are_enforced(self):
        from http.client import HTTPConnection
        raw = canonical(self.query).encode('utf-8')
        for payload, suffix, expected in (
            (raw + b' ' * 4096, '', 413),
            (raw[:-1] + b',"schema_version":3}', '', 400),
            (raw, '?extra=1', 400),
        ):
            connection = HTTPConnection('127.0.0.1', self.f.server.server_port, timeout=6)
            try:
                connection.request('POST', '/api'+PATH+suffix, body=payload,
                    headers={'Authorization':'Bearer '+self.f.full, 'Content-Type':'application/json'})
                response = connection.getresponse()
                result = json.loads(response.read())
                self.assertEqual(response.status, expected, result)
                self.assertNotIn('request_resolution', result)
            finally:
                connection.close()
        grant = self.f.call('/business/offline/access/v2', {}, status=201)
        self.f.call(PATH, self.query, token=grant['token'],
            headers={'X-Smartplan-Offline-Binding':self.f.instance+':'+self.f.account}, status=403)


if __name__ == '__main__':
    unittest.main()
