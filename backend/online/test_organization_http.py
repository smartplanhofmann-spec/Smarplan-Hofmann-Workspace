"""Real authenticated HTTP company setup, no external providers or live records."""
import uuid
import unittest

from online import test_plan_imports as fixture


class OrganizationHttpTests(unittest.TestCase):
    setUp = fixture.PlanImportApiTests.setUp
    tearDown = fixture.PlanImportApiTests.tearDown
    open_app = fixture.PlanImportApiTests.open_app
    call = fixture.PlanImportApiTests.call

    def body(self, value):
        return dict(request_id=uuid.uuid4().hex, revision=value['revision'], needs=value['needs'],
            modules={key: dict(visible=item['visibility_override'], enabled=item['enabled'])
                     for key, item in value['modules'].items()})

    def test_onboarding_employee_suggestion_manual_override_and_history(self):
        config = self.call('GET', '/business/organization').json
        self.assertFalse(config['modules']['personnel']['visible'])
        self.call('GET', '/business/organization', token=None, status=401)
        employee = self.call('POST', '/business/employees', dict(request_id=uuid.uuid4().hex,
            user_id=self.owner_id, name='Synthetic owner working in the business'), status=201).json
        config = self.call('GET', '/business/organization').json
        self.assertTrue(config['modules']['personnel']['visible'])
        body = self.body(config)
        body['modules']['personnel'] = dict(visible=False, enabled=False)
        saved = self.call('POST', '/business/organization', body).json
        self.assertEqual(saved, self.call('POST', '/business/organization', body).json)
        self.call('POST', '/business/time/events', {'request_id': uuid.uuid4().hex}, status=423)
        retained = self.call('GET', '/business/employees').json['items']
        self.assertEqual(retained[0]['id'], employee['id'])
        meta = self.call('GET', '/business/capabilities').json
        self.assertIn('organization_modules', meta['features'])
        self.assertEqual(meta['organization']['modules']['personnel'], {'visible': False, 'enabled': False})

    def test_query_and_field_injection_never_selects_another_company(self):
        self.call('GET', '/business/organization?company_id=foreign', status=400)
        config = self.call('GET', '/business/organization').json
        body = self.body(config)
        body['company_id'] = 'foreign'
        self.call('POST', '/business/organization', body, status=400)
        self.assertEqual(self.call('GET', '/business/organization').json['revision'], 0)


if __name__ == '__main__':
    unittest.main()
