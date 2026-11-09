"""Actual MFA and fresh account/resource separation for browser wrapping keys."""
import base64
import copy
import unittest

from core import canonical, Problem
from online.client_originals import wrapping_key
from online import test_business_travel_mileage_http as mileage_fixture
from online import test_purchasing_journey as purchasing_fixture
from online.web import create_app


class BrowserOriginalKeyTests(unittest.TestCase):
    call = mileage_fixture.MileageHttpTests.call
    login = mileage_fixture.MileageHttpTests.login

    def setUp(self):
        self.domain = mileage_fixture.MileageHttpTests('runTest')
        self.domain.setUp()
        self.addCleanup(self.domain.doCleanups)
        self.office = self.domain.office
        self.f = self.domain.f
        self.app, self.client = self.domain.app, self.domain.client
        self.token, self.tech = self.domain.token, self.domain.tech

    def key(self, kind='private_car_mileage', subject=None, token=None, status=200):
        return self.call('GET', '/business/client-original-key?kind='+kind+
                         '&subject_id='+(subject or self.f.employee['id']), token=token, status=status)

    def test_actual_authenticated_key_is_stable_separate_and_never_master_material(self):
        caps = self.call('GET', '/business/capabilities').json
        self.assertIn('client_original_key', caps['features'])
        owner = self.key()
        self.assertEqual(owner.headers['Cache-Control'], 'no-store')
        self.assertNotIn('ETag', owner.headers)
        self.assertEqual(owner.json, self.key().json)
        self.assertEqual(len(base64.b64decode(owner.json['wrapping_key'], validate=True)), 32)
        self.assertNotEqual(owner.json['wrapping_key'], self.f.key.decode())
        self.assertNotEqual(base64.b64decode(owner.json['wrapping_key']),
                            base64.urlsafe_b64decode(self.f.key))
        self.assertEqual(owner.json['binding'], dict(schema_version=1,
            instance_id=self.f.instance, account_id=self.f.owner['id'], host='travel.example.test',
            api_version='v1', kind='private_car_mileage', subject_id=self.f.employee['id']))
        employee = self.key(token=self.tech).json
        self.assertNotEqual(employee['wrapping_key'], owner.json['wrapping_key'])
        self.assertEqual(employee['binding']['account_id'], self.f.technician['id'])
        project = self.key('material_return', self.f.project).json
        self.assertNotEqual(project['wrapping_key'], owner.json['wrapping_key'])

    def test_same_verified_server_recreation_keeps_only_the_same_derived_key(self):
        before = self.key().json
        self.client = create_app(office=self.office, key=self.f.key, host='travel.example.test',
            storage=self.f.storage, instance_id=self.f.instance).test_client()
        self.assertEqual(self.key().json, before)

    def test_instance_mismatch_is_rejected_and_other_project_key_is_separate(self):
        # Real authorized calls above prove HTTP wiring; direct derivations here
        # do not weaken the verified instance or authenticated actor checks.
        first = self.key().json
        other_project = self.office.add_project(self.f.owner, 'Other synthetic project', 'Synthetic other')
        self.assertNotEqual(self.key('material_return', other_project).json['wrapping_key'],
                            self.key('material_return', self.f.project).json['wrapping_key'])
        before = canonical(first)
        with self.assertRaises(Problem) as caught:
            wrapping_key(self.office, self.f.owner, {'kind':'private_car_mileage',
                'subject_id':self.f.employee['id']}, master_key=self.f.key,
                instance={'instance_id':'f'*32,'public_host':'travel.example.test'},host='travel.example.test')
        self.assertEqual(caught.exception.status,409)
        self.assertEqual(canonical(self.key().json), before)

    def test_private_key_does_not_follow_missing_employee_or_fresh_inactive_identity(self):
        self.key(subject='f'*32, status=404)
        self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.f.technician['id'],))
        self.key(token=self.tech, status=401)
        self.office.db.execute('UPDATE users SET active=1 WHERE id=?', (self.f.technician['id'],))
        self.assertEqual(self.key(token=self.tech).json['binding']['account_id'], self.f.technician['id'])

    def test_global_inventory_grant_does_not_survive_actual_project_assignment_revocation(self):
        self.call('POST', '/business/settings/permissions', dict(request_id='a'*32,
            user_id=self.f.technician['id'], permission='inventory.read', scope='*', effect='allow', revision=0))
        self.key('material_return', self.f.project, token=self.tech)
        self.office.db.execute('DELETE FROM assignments WHERE project_id=? AND user_id=?',
            (self.f.project, self.f.technician['id']))
        self.key('material_return', self.f.project, token=self.tech, status=404)

    def test_personnel_deny_is_checked_again_before_releasing_same_resource_key(self):
        hr=self.call('POST','/users',dict(email='synthetic-key-hr@example.test',
            password='Synthetic-key-hr-password-123',role='technician'),status=201).json['id']
        token=self.login('synthetic-key-hr@example.test','Synthetic-key-hr-password-123')
        self.call('POST', '/business/settings/permissions', dict(request_id='b'*32,
            user_id=hr, permission='personnel.read', scope='*', effect='allow', revision=0))
        before=self.key(token=token).json
        self.call('POST', '/business/settings/permissions', dict(request_id='c'*32,
            user_id=hr, permission='personnel.read', scope='*', effect='deny', revision=1))
        self.key(token=token,status=403)
        self.call('POST', '/business/settings/permissions', dict(request_id='d'*32,
            user_id=hr, permission='personnel.read', scope='*', effect='allow', revision=2))
        self.assertEqual(self.key(token=token).json,before)

    def test_strict_shape_method_and_get_body_never_release_key(self):
        path='/business/client-original-key'
        for query in ['', '?kind=private_car_mileage', '?kind=unknown&subject_id='+'a'*32,
          '?kind=private_car_mileage&subject_id='+'a'*32+'&account_id='+self.f.owner['id'],
          '?kind=private_car_mileage&kind=material_return&subject_id='+'a'*32]:
            self.call('GET',path+query,status=400)
        self.call('POST',path,{},status=405)
        response=self.client.get('/api/v1'+path+'?kind=private_car_mileage&subject_id='+self.f.employee['id'],
            base_url='https://travel.example.test',data=b'{}',content_type='application/json',
            headers={'Authorization':'Bearer '+self.token})
        self.assertEqual(response.status_code,400)
        self.assertNotIn('wrapping_key',response.json)

    def test_key_reads_do_not_add_payments_claims_or_personnel_originals(self):
        tables=('business_travel_requests','business_travel_payments','business_travel_claims',
                'business_stock_movements','business_personnel_files')
        def snapshot():
            return {name:[dict(row) for row in self.office.db.execute('SELECT * FROM '+name)] for name in tables}
        before=copy.deepcopy(snapshot())
        for _ in range(3):self.key();self.key('material_return',self.f.project)
        self.assertEqual(snapshot(),before)

    def test_unbound_server_does_not_advertise_or_release_browser_key(self):
        other=purchasing_fixture.PurchasingJourneyTests('runTest');other.setUp();self.addCleanup(other.doCleanups)
        caps=other.call('/business/capabilities').json
        self.assertNotIn('client_original_key',caps['features'])
        response=other.call('/business/client-original-key?kind=material_return&subject_id='+other.project,status=409)
        self.assertNotIn('wrapping_key',response.json)

    def test_readonly_history_keeps_same_key_without_releasing_write_authority(self):
        from business_schema import set_mode
        before=self.key().json
        set_mode(self.office,'legacy')
        self.assertEqual(self.key().json,before)
        self.call('POST','/business/personnel/travel/mileage/trips',self.domain.x.input,
                  token=self.tech,status=409)

    def test_actual_bound_offline_device_token_cannot_obtain_decryption_material(self):
        grant=self.call('POST','/offline/access/v2',{},token=self.tech,status=201).json
        self.assertTrue(grant['token'].startswith('offline_workspace_v2_'))
        response=self.client.get('/api/v1/business/client-original-key?kind=private_car_mileage&subject_id='+self.f.employee['id'],
            base_url='https://travel.example.test',headers={'Authorization':'Bearer '+grant['token'],
            'X-Smartplan-Offline-Binding':self.f.instance+':'+self.f.technician['id']})
        self.assertEqual(response.status_code,403)
        self.assertNotIn('wrapping_key',response.json)


if __name__=='__main__':unittest.main()
