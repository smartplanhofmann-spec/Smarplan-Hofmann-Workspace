"""Actual milestone records across schema, export and subject-source boundaries."""
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tempfile
import unittest
import uuid
import zipfile

import business_api
import business_schema
from business_organization import Organization
from business_planning import Planning
from business_project_milestones import ProjectMilestones
from company_export_archive import build, structure, verify
from company_export_catalog import COLUMNS
from core import Office, Problem
from privacy_case_sources import inventory, resolve


TABLES = ('business_project_milestones', 'business_project_milestone_versions',
          'business_project_milestone_requests')


def request(**values):
    return dict(request_id=uuid.uuid4().hex, **values)


class ProjectMilestoneCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-milestone-catalog-')
        self.addCleanup(self.temp.cleanup)
        self.office = Office(Path(self.temp.name) / 'office.db')
        self.addCleanup(self.office.db.close)
        self.now = datetime(2026, 11, 9, 12, tzinfo=timezone.utc)
        self.owner = self.actor('owner')
        self.worker = self.actor('technician')
        self.other = self.actor('manager')
        self.customer = self.office.create_customer(self.owner, dict(name='Synthetic milestone customer'))
        self.foreign_customer = self.office.create_customer(self.owner, dict(name='Unrelated customer'))
        self.project = self.office.add_project(self.owner, 'Synthetic milestones', customer_id=self.customer['id'])
        self.foreign_project = self.office.add_project(self.owner, 'Unrelated project', customer_id=self.foreign_customer['id'])
        for actor in (self.worker, self.other):
            self.office.assign(self.owner, self.project, actor['id'])
        self.service = ProjectMilestones(self.office, clock=lambda: self.now)

    def actor(self, role):
        return dict(id=self.office.add_user(role + '@example.test', 'Synthetic-password-123', role), role=role)

    def body(self, **changes):
        values = dict(schema_version=1, title='Synthetic milestone', details='', due_date=None,
            assignee_id=None, status='planned')
        values.update(changes)
        return request(**values)

    def create(self, *, project=None, title='Synthetic milestone', assignee=None, details=''):
        return self.service.create(self.owner, project or self.project,
            self.body(title=title, assignee_id=assignee, details=details))

    def revised(self, value, **changes):
        fields = {key: value[key] for key in ('title', 'details', 'due_date', 'assignee_id', 'status')}
        fields.update(changes)
        return self.service.update(self.owner, self.project, value['id'],
            request(schema_version=1, revision=value['revision'], **fields))

    def test_actual_records_export_with_all_versions_but_no_retry_requests(self):
        initial = self.create()
        latest = self.revised(initial, title='Explicit revised milestone')
        items = structure(self.office)
        for table in TABLES:
            actual = next(item for item in items if item['table'] == table)
            self.assertEqual([column['name'] for column in actual['columns']], COLUMNS[table].split(','))
            self.assertTrue(actual['sensitive'])
            self.assertIsNone(actual['retention_days'])
            self.assertEqual(actual['included'], not table.endswith('_requests'))
        raw, manifest = build(self.office, instance_id='a' * 32, export_id=uuid.uuid4().hex,
            created_at=self.now.isoformat(), created_by=self.owner['id'], reason='Synthetic bounded export', inventory=items)
        self.assertTrue(verify(raw, instance_id='a' * 32)['valid'])
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            def rows(table):
                return [json.loads(line) for line in archive.read('data/' + table + '.jsonl').splitlines()]
            self.assertNotIn('data/business_project_milestone_requests.jsonl', archive.namelist())
            current = rows('business_project_milestones')
            self.assertEqual(len(current), 1)
            self.assertEqual(current[0]['id'], latest['id'])
            versions = [json.loads(row['payload_json']) for row in rows('business_project_milestone_versions')]
            self.assertEqual([row['title'] for row in versions], [initial['title'], latest['title']])
            self.assertEqual([row['content_hash'] for row in versions], [initial['content_hash'], latest['content_hash']])
        exported = {table['table'] for table in manifest['tables']}
        self.assertTrue(set(TABLES[:2]) <= exported)
        self.assertNotIn(TABLES[2], exported)

    def test_customer_sources_follow_project_and_keep_historical_versions(self):
        first = self.create()
        self.revised(first, details='Explicitly corrected project milestone')
        unrelated = self.create(project=self.foreign_project, title='Unrelated milestone')
        sources = inventory(self.office, self.owner, 'customer', self.customer['id'])['sources']
        current = [row for row in sources if row['table'] == TABLES[0]]
        historical = [row for row in sources if row['table'] == TABLES[1]]
        self.assertEqual([row['primary_key']['id'] for row in current], [first['id']])
        self.assertEqual({row['primary_key']['revision'] for row in historical}, {1, 2})
        self.assertNotIn(unrelated['id'], json.dumps(current + historical))
        for descriptor in current + historical:
            record, blobs = resolve(self.office, self.owner, descriptor, export=True)
            self.assertEqual(record['project_id'], self.project)
            self.assertEqual(blobs, {})

    def test_assignee_source_includes_historical_assignment_without_free_text_guessing(self):
        assigned = self.create(assignee=self.worker['id'])
        latest = self.revised(assigned, assignee_id=self.other['id'])
        unrelated = self.create(title='Not a person link', details=self.worker['id'])
        employee = Planning(self.office, clock=lambda: self.now).save_employee(self.owner,
            request(user_id=self.worker['id'], name='Synthetic assigned employee'))
        for kind, identifier in (('user', self.worker['id']), ('employee', employee['id'])):
            result = inventory(self.office, self.owner, kind, identifier)
            sources = [row for row in result['sources'] if row['table'] in TABLES[:2]]
            self.assertTrue(sources)
            original = [row for row in sources if row['table'] == TABLES[1] and row['primary_key']['revision'] == 1]
            self.assertTrue(original)
            value, _ = resolve(self.office, self.owner, original[0], export=True)
            self.assertEqual(value['payload_json']['assignee_id'], self.worker['id'])
            self.assertNotIn(unrelated['id'], json.dumps(sources))
            self.assertEqual(result['completeness'], 'manual_review_required')
        self.assertEqual(latest['assignee_id'], self.other['id'])

    def test_intermediate_historical_editor_is_a_structured_subject_source(self):
        original = self.create()
        changed = self.service.update(self.other, self.project, original['id'],
            request(schema_version=1, revision=1, title='Intermediate editor', details='', due_date=None,
                    assignee_id=None, status='planned'))
        self.revised(changed, title='Owner later revision')
        unrelated = self.create(details=self.other['id'])
        result = inventory(self.office, self.owner, 'user', self.other['id'])
        histories = [row for row in result['sources'] if row['table'] == TABLES[1]]
        match = [row for row in histories if row['primary_key']['milestone_id'] == original['id']
                 and row['primary_key']['revision'] == 2]
        self.assertEqual(len(match), 1)
        value, _ = resolve(self.office, self.owner, match[0], export=True)
        self.assertEqual(value['payload_json']['updated_by'], self.other['id'])
        self.assertNotIn(unrelated['id'], json.dumps(histories))

    def test_planning_pause_blocks_router_writes_and_retains_original_reads(self):
        original = self.create()
        organization = Organization(self.office)
        state = organization.get(self.owner)
        body = request(revision=state['revision'], needs=state['needs'],
            modules={key: dict(visible=value['visibility_override'], enabled=value['enabled'])
                     for key, value in state['modules'].items()})
        body['modules']['planning']['enabled'] = False
        organization.save(self.owner, body)
        route = '/business/projects/' + self.project + '/milestones'
        with self.assertRaises(Problem) as failure:
            business_api.dispatch(self.office, self.owner, route, 'POST', self.body())
        self.assertEqual(failure.exception.status, 423)
        value, status, _ = business_api.dispatch(self.office, self.owner, route + '/' + original['id'], 'GET', {})
        self.assertEqual(status, 200)
        self.assertEqual(value['id'], original['id'])
        history, status, _ = business_api.dispatch(self.office, self.owner, route + '/' + original['id'] + '/history', 'GET', {})
        self.assertEqual(status, 200)
        self.assertTrue(history)
        self.assertTrue(business_api.strict_workflow_path(route))
        self.assertTrue(business_api.strict_workflow_path(route + '/' + original['id'] + '/history'))
        self.assertFalse(business_api.strict_workflow_path(route + '/' + original['id'] + '/history/extra'))
        self.assertIn('project_milestones', business_api.capabilities(self.office, self.owner)['features'])


if __name__ == '__main__':
    unittest.main()
