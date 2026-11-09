"""Real MFA/HTTP milestone contracts across two isolated synthetic companies."""
import json
import os
import unittest
import uuid

from business_foundation import BusinessFoundation
from online import test_instance_isolation as isolation_fixture


@unittest.skipUnless(os.name == 'posix', 'Private POSIX synthetic storage required')
class ProjectMilestoneHttpTests(unittest.TestCase):
    setUp = isolation_fixture.InstanceIsolationTests.setUp
    fixture = isolation_fixture.InstanceIsolationTests.fixture
    bind = isolation_fixture.InstanceIsolationTests.bind
    app = isolation_fixture.InstanceIsolationTests.app
    request = isolation_fixture.InstanceIsolationTests.request
    login = isolation_fixture.InstanceIsolationTests.login
    start = isolation_fixture.InstanceIsolationTests.start

    def command(self, **changes):
        value = dict(schema_version=1, request_id=uuid.uuid4().hex,
                     title=' Projektübergabe 🚧 ', details='Original\nmit Abschlusszeile.\n',
                     due_date='2026-11-30', assignee_id=None, status='planned')
        value.update(changes)
        return value

    def test_create_update_original_replay_and_complete_history_cross_transport(self):
        company = self.start(self.company[0]); token = company['token']
        path = '/business/projects/' + company['project'] + '/milestones'
        body = self.command()
        original = self.request(company, path, body, token=token, status=201).json
        self.assertEqual(original['title'], body['title'])
        self.assertEqual(original['details'], body['details'])
        changed = self.command(revision=1, status='achieved')
        current = self.request(company, path + '/' + original['id'], changed, token=token).json
        self.assertEqual(self.request(company, path, body, token=token, status=201).json, original)
        self.assertEqual(self.request(company, path + '/' + original['id'], changed, token=token).json, current)
        self.assertEqual(self.request(company, path + '/' + original['id'] + '/history', token=token).json,
                         dict(schema_version=1, project_id=company['project'], milestone_id=original['id'], items=[original, current]))
        self.assertEqual(self.request(company, path, token=token).json['items'], [current])
        conflict = self.request(company, path + '/' + original['id'], self.command(revision=1), token=token, status=409).json
        self.assertEqual(conflict['request_resolution'], 'not_accepted')
        collision = self.request(company, path, body | {'title':'Andere Eingabe'}, token=token, status=409).json
        self.assertNotIn('request_resolution', collision)

    def test_current_project_and_planning_rights_are_required_on_every_original_read(self):
        first, second = [self.start(value) for value in self.company]
        path = '/business/projects/' + first['project'] + '/milestones'
        body = self.command(); original = self.request(first, path, body, token=first['token'], status=201).json
        self.request(second, path, token=second['token'], status=404)
        self.request(first, path, token=second['token'], status=401)
        user = self.request(first, '/users', dict(email='milestone-reader@example.test', password='Synthetic-reader-password', role='technician'),
                            token=first['token'], status=201).json['id']
        actor = first['office'].user(first['token'])
        first['office'].assign(actor, first['project'], user)
        token = self.login(first, 'milestone-reader@example.test', 'Synthetic-reader-password')
        self.request(first, path + '/' + original['id'] + '/history', token=token)
        self.request(first, path, self.command(), token=token, status=403)
        BusinessFoundation(first['office']).save_grant(actor, dict(request_id=uuid.uuid4().hex, user_id=user, permission='planning.read',
            scope=first['project'], effect='deny', revision=0))
        self.request(first, path, token=token, status=403)
        self.request(first, path + '/' + original['id'], token=token, status=403)

    def test_strict_json_routes_and_offline_access(self):
        company = self.start(self.company[0]); token = company['token']
        path = '/business/projects/' + company['project'] + '/milestones'
        original = self.request(company, path, self.command(), token=token, status=201).json
        self.request(company, path + '?project_id=foreign', token=token, status=400)
        self.request(company, path + '/' + original['id'] + '/history?limit=1', token=token, status=400)
        self.request(company, path, {}, token=token, status=405, method='PATCH')
        self.request(company, path + '/' + original['id'] + '/history', {}, token=token, status=405)
        response = company['client'].open('/api/v1' + path, method='POST', base_url='https://' + company['host'],
            data='{"schema_version":1,"schema_version":2}', content_type='application/json',
            headers={'Authorization':'Bearer ' + token})
        self.assertEqual(response.status_code, 400)
        for field, invalid in (('title', '\ud800'), ('details', '\udfff')):
            self.request(company, path, self.command(**{field:invalid}), token=token, status=400)
        device = self.request(company, '/business/offline/access', {}, token=token, status=201).json['token']
        self.request(company, path, token=device, status=403)
        self.request(company, path, self.command(), token=device, status=403)
        meta = self.request(company, '/business/capabilities', token=token).json
        self.assertIn('project_milestones', meta['features'])


if __name__ == '__main__':
    unittest.main()
