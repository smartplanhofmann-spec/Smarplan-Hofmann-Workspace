"""Current originals/search/events/exports through two actual loopback processes.

Independent SQLite databases/processes, real MFA/HTTP/domain code and synthetic
data only. This does not claim PostgreSQL-role, different-UID or deployment
acceptance. The shared scenario is reused by the separate PostgreSQL test.
"""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import uuid
import zipfile

from cryptography.fernet import Fernet

from core import Office
from online.auth import totp
from online.instance import bind
from online.storage import Storage
from online.test_instance_isolation import MFA_SCHEMA


PASSWORD = 'Synthetic-company-isolation-password-2026'
PARSER_PYTHON = os.environ.get('SMARTPLAN_TEST_PARSER_PYTHON')


def req(**values):
    return dict(request_id=uuid.uuid4().hex, **values)


def serve_company(value, ports):
    from werkzeug.serving import make_server, WSGIRequestHandler
    from online.web import create_app
    os.environ.update(SMARTPLAN_INSTANCE_ID=value['instance_id'],
        SMARTPLAN_PUBLIC_HOST=value['host'], SMARTPLAN_ASSISTANT_ENABLED='0',
        SMARTPLAN_ASSISTANT_SPEECH_ENABLED='0')
    office = Office(value['database'])
    storage = Storage(office, value['key'], value['host'], config={'server': {'path': value['storage']}})
    app = create_app(office=office, key=value['key'], host=value['host'], storage=storage,
        instance_id=value['instance_id'])
    class Quiet(WSGIRequestHandler):
        def log(self, *args, **kwargs):
            pass
    server = make_server('127.0.0.1', 0, app, request_handler=Quiet)
    ports.put(dict(port=server.server_port, pid=os.getpid()))
    try:
        server.serve_forever()
    finally:
        server.server_close()
        office.db.close()


def process_company_import(value, results):
    """Separate actual worker/parser processes; synthetic development sandbox only."""
    from online.instance import verify_worker
    from online.import_sandbox import DevelopmentRunner
    from online.import_worker import work_one
    os.environ.update(SMARTPLAN_INSTANCE_ID=value['instance_id'], SMARTPLAN_PUBLIC_HOST=value['host'])
    if 'dsn' in value:
        from online.store import PostgresOffice
        os.environ.update(value['privacy'])
        office = PostgresOffice(value['dsn'], instance_roles=value['company'].roles)
    else:
        office = Office(value['database'])
    try:
        verify_worker(office)
        result = work_one(office, runner=DevelopmentRunner(PARSER_PYTHON))
        results.put(dict(pid=os.getpid(), result=result))
    finally:
        office.db.close()


class CurrentCompanyScenario:
    def call(self, company, path, body=None, *, token='owner', status=200, raw=False, host=None, method=None):
        headers = {'Host': host or company['host'], 'X-Forwarded-Proto': 'https', 'Content-Type': 'application/json'}
        if isinstance(body, bytes):
            headers['Content-Type'] = 'application/octet-stream'
        bearer = company.get('token') if token == 'owner' else token
        if bearer:
            headers['Authorization'] = 'Bearer ' + bearer
        request = urllib.request.Request('http://127.0.0.1:' + str(company['port']) + '/api/v1' + path,
            data=body if isinstance(body, bytes) else None if body is None else json.dumps(body).encode(),
            headers=headers, method=method)
        try:
            response = urllib.request.urlopen(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            data = response.read()
            self.assertEqual(response.status, status, (path, response.status, data[:150] if status != response.status else ''))
            self.assertEqual(response.headers.get('Cache-Control'), 'no-store')
            self.assertNotIn('Access-Control-Allow-Origin', response.headers)
        return data if raw else (json.loads(data) if data else None)

    def login(self, company, *, email='same-owner@example.test', password=None):
        password = password or company.get('password', PASSWORD)
        challenge = self.call(company, '/login', dict(email=email, password=password), token=None)
        self.assertNotIn('token', challenge)
        return self.call(company, '/login/verify', dict(challenge=challenge['challenge'],
            code=totp(challenge['enrollment']['secret'], int(time.time() // 30))), token=None)['token']

    def initialize_http(self):
        for value in self.companies:
            value['token'] = self.login(value)
            value['owner'] = self.call(value, '/me')
            value['project'] = self.call(value, '/projects', dict(name=value['marker'] + ' project',
                customer=value['marker'] + ' buyer'), status=201)['id']
        self.assertNotEqual(self.companies[0]['pid'], self.companies[1]['pid'])
        self.assertNotEqual(self.companies[0]['token'], self.companies[1]['token'])

    def catalog(self, company, *, request_id):
        adapter = self.call(company, '/business/adapters', req(name=company['marker'] + ' source',
            profile='catalog_csv_v1', enabled=True), status=201)
        raw = ('code;name;unit;cost_price_net;unit_price_net;tax_rate\r\n'
            'SAME-CODE;' + company['marker'] + ' original;ST;1.25;2.50;19\r\n').encode()
        body = dict(request_id=request_id, filename='same-filename.csv', content_base64=base64.b64encode(raw).decode())
        run = self.call(company, '/business/adapters/' + adapter['id'] + '/import', body, status=201)
        path = '/business/adapters/imports/' + run['id']
        self.assertEqual(self.call(company, path + '/original', raw=True), raw)
        preview = self.call(company, path + '/catalog-preview', {})
        self.assertEqual(preview['rows'][0]['action'], 'create')
        accepted = self.call(company, path + '/apply', req(confirmed=True))
        self.assertEqual(accepted['source_sha256'], hashlib.sha256(raw).hexdigest())
        self.assertEqual(self.call(company, '/business/adapters/' + adapter['id'] + '/import', body, status=201), accepted)
        company.update(adapter=adapter, catalog=accepted, catalog_bytes=raw)

    def export(self, company, *, request_id):
        state = self.call(company, '/business/company-handover')
        self.assertTrue(state['ready'], state['blockers'])
        command = dict(request_id=request_id, instance_id=company['instance_id'],
            catalog_sha256=state['catalog_sha256'], reason='Synthetic current isolation acceptance',
            confirmation=True, sensitive_data_confirmed=True)
        value = self.call(company, '/business/company-handover/exports', command, status=201)
        self.assertEqual(self.call(company, '/business/company-handover/exports', command, status=201), value)
        raw = self.call(company, '/business/company-handover/exports/' + value['id'] + '/archive', raw=True)
        from company_export_archive import verify
        self.assertTrue(verify(raw, instance_id=company['instance_id'])['valid'])
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            unpacked = {name: archive.read(name) for name in archive.namelist()}
        self.assertEqual(json.loads(unpacked['manifest.json'])['instance_id'], company['instance_id'])
        projects = [json.loads(line) for line in unpacked['data/projects.jsonl'].splitlines()]
        self.assertEqual([row['id'] for row in projects], [company['project']])
        self.assertIn(company['catalog_bytes'], unpacked.values())
        company.update(export=value, export_body=command, archive=raw, unpacked=unpacked)

    def current_originals_search_and_export(self):
        self.initialize_http()
        original_nonce, export_nonce = uuid.uuid4().hex, uuid.uuid4().hex
        for company in self.companies:
            self.catalog(company, request_id=original_nonce)
            self.export(company, request_id=export_nonce)
        for own, foreign in (self.companies, self.companies[::-1]):
            self.call(own, '/business/adapters/imports/' + own['catalog']['id'] + '/original', token=foreign['token'], status=401)
            self.call(own, '/business/adapters/imports/' + foreign['catalog']['id'] + '/original', status=404)
            self.call(own, '/business/adapters/' + foreign['adapter']['id'] + '/imports', status=404)
            own_search = self.call(own, '/business/articles?query=' + own['marker'])
            self.assertEqual(len(own_search['items']), 1)
            self.assertEqual(self.call(own, '/business/articles?query=' + foreign['marker'])['items'], [])
            self.call(own, '/business/company-handover/exports/' + foreign['export']['id'] + '/archive', status=404)
            self.call(own, '/business/company-handover/exports', foreign['export_body'], status=409)
            self.call(own, '/business/company-handover/exports/' + own['export']['id'] + '/archive', token=foreign['token'], status=401)
            for name, content in own['unpacked'].items():
                self.assertNotIn(foreign['marker'].encode(), content, name)
            self.assertNotIn(own['token'].encode(), b'\n'.join(own['unpacked'].values()))
            self.assertEqual(self.call(own, '/business/adapters/imports/' + own['catalog']['id'] + '/original', raw=True), own['catalog_bytes'])
            self.call(own, '/projects', host=foreign['host'], status=400)

    def current_context_events_and_same_rule_ids(self):
        self.initialize_http()
        rule_id, rule_nonce, context_nonce, scan_nonce = [uuid.uuid4().hex for _ in range(4)]
        for company in self.companies:
            task = self.call(company, '/projects/' + company['project'] + '/tasks', req(title=company['marker'] + ' overdue',
                details=company['marker'] + ' original task details', status='todo', priority='normal',
                due_date=(datetime.now(timezone.utc) - timedelta(days=4)).date().isoformat(), assignee_id=company['owner']['id']), status=201)
            context = self.call(company, '/business/assistant/contexts', dict(request_id=context_nonce,
                project_id=company['project'], sources=[dict(kind='project', id=company['project']), dict(kind='task', id=task['id'])]))
            rule = dict(request_id=rule_nonce, id=rule_id, revision=0, title=company['marker'] + ' event rule', enabled=True,
                project_ids=[company['project']], trigger='task.overdue', action='task.create', mode='approval', conditions=[],
                template=dict(title=company['marker'] + ' followup', details='Synthetic internal action only', priority='normal', due_days=None),
                responsible_id=company['owner']['id'], confirmation=True)
            saved = self.call(company, '/business/company-events/rules', rule)
            self.assertEqual(saved['id'], rule_id)
            scan = self.call(company, '/business/company-events/scan', dict(request_id=scan_nonce, limit=100, after=None))
            self.assertEqual(len(scan['items']), 1)
            plan_id = scan['items'][0]['plan_ids'][0]
            plan = self.call(company, '/business/company-events/plans/' + plan_id)
            company.update(context=context, rule=saved, plan=plan, scan=scan, task=task)
        for own, foreign in (self.companies, self.companies[::-1]):
            self.call(own, '/business/assistant/contexts/' + foreign['context']['id'], status=404)
            self.call(own, '/business/assistant/contexts', req(project_id=own['project'], sources=[dict(kind='task', id=foreign['task']['id'])]), status=404)
            self.call(own, '/business/company-events/plans/' + foreign['plan']['id'], status=404)
            self.call(own, '/business/company-events/runs/' + foreign['scan']['id'], status=404)
            history = self.call(own, '/business/company-events/rules/' + rule_id + '/history')
            self.assertEqual(history['items'][0]['project_ids'], [own['project']])
            self.assertNotIn(foreign['marker'], json.dumps(own['context']))
            approval = req(plan_sha256=own['plan']['sha256'], confirmation=True, reason='Explicit synthetic own-company action')
            self.call(own, '/business/company-events/plans/' + own['plan']['id'] + '/approve', approval)
            execute = req(plan_sha256=own['plan']['sha256'], confirmation=True)
            result = self.call(own, '/business/company-events/plans/' + own['plan']['id'] + '/execute', execute)
            self.assertEqual(result['status'], 'succeeded')
            self.assertEqual(self.call(own, '/business/company-events/plans/' + own['plan']['id'] + '/execute', execute), result)
            self.call(foreign, '/business/company-events/plans/' + own['plan']['id'] + '/execute', execute, status=404)
            tasks = self.call(own, '/projects/' + own['project'] + '/tasks')
            self.assertEqual(len(tasks), 2)
            self.assertTrue(all(foreign['marker'] not in json.dumps(value) for value in tasks))

    def current_private_originals_and_fresh_permissions(self):
        self.initialize_http()
        upload_nonce = uuid.uuid4().hex
        for company in self.companies:
            employee = self.call(company, '/business/employees', req(user_id=company['owner']['id'],
                name=company['marker'] + ' personnel', weekly_minutes=2400, hourly_cost_minor=3500), status=201)
            content = ('%PDF-1.4\n' + company['marker'] + ' private original\n%%EOF').encode()
            command = dict(request_id=upload_nonce, employee_id=employee['id'], purpose='personnel',
                owner_visible=False, filename='identical-private-original.pdf', media_type='application/pdf',
                content_base64=base64.b64encode(content).decode())
            original = self.call(company, '/business/personnel/files', command)
            self.assertEqual(self.call(company, '/business/personnel/files', command), original)
            reader = self.call(company, '/users', dict(email='same-reader@example.test', password=PASSWORD,
                role='accountant'), status=201)
            token = self.login(company, email='same-reader@example.test', password=PASSWORD)
            company.update(employee=employee, private_original=original, private_bytes=content,
                reader_id=reader['id'], reader_token=token)
        for own, foreign in (self.companies, self.companies[::-1]):
            path = '/business/personnel/files/' + own['private_original']['id'] + '/content'
            listing = '/business/personnel/files?employee_id=' + own['employee']['id']
            self.assertEqual(self.call(own, path, raw=True), own['private_bytes'])
            self.call(own, path, token=foreign['token'], status=401)
            self.call(own, '/business/personnel/files/' + foreign['private_original']['id'] + '/content', status=404)
            self.call(own, '/business/personnel/files?employee_id=' + foreign['employee']['id'], status=404)
            self.call(own, path, token=own['reader_token'], status=403)
            permission = dict(user_id=own['reader_id'], permission='personnel.read', scope='*')
            self.call(own, '/business/settings/permissions', req(**permission, effect='allow', revision=0))
            self.assertEqual(self.call(own, path, token=own['reader_token'], raw=True), own['private_bytes'])
            self.assertEqual([v['id'] for v in self.call(own, listing, token=own['reader_token'])['items']],
                [own['private_original']['id']])
            # The same authenticated session must lose its download right immediately.
            self.call(own, '/business/settings/permissions', req(**permission, effect='deny', revision=1))
            self.call(own, path, token=own['reader_token'], status=403)
            self.call(own, listing, token=own['reader_token'], status=403)
            self.assertEqual(self.call(own, path, raw=True), own['private_bytes'])

    def current_queue_and_actual_parser_processes(self):
        from PIL import Image, PngImagePlugin
        self.initialize_http()
        nonce = uuid.uuid4().hex
        for index, company in enumerate(self.companies):
            output = io.BytesIO()
            metadata = PngImagePlugin.PngInfo()
            metadata.add_text('synthetic_company', company['marker'])
            Image.new('RGB', (96, 72), ('white', 'lightgray')[index]).save(output, format='PNG', pnginfo=metadata)
            raw = output.getvalue()
            path = '/projects/' + company['project'] + '/plan-imports'
            body = dict(request_id=nonce, filename='identical-plan.png', media_type='image/png',
                size=len(raw), sha256=hashlib.sha256(raw).hexdigest(), page=0, title=company['marker'] + ' floor')
            job = self.call(company, path, body, status=201)
            job_path = path + '/' + job['id']
            self.call(company, job_path + '/chunks/0', raw, method='PUT')
            self.assertEqual(self.call(company, job_path + '/complete', {})['status'], 'queued')
            self.assertEqual(self.call(company, job_path + '/source', raw=True), raw)
            company.update(import_job=job, import_path=job_path, import_bytes=raw)
        for own, foreign in (self.companies, self.companies[::-1]):
            self.call(own, foreign['import_path'] + '/source', status=404)
            self.call(own, '/projects/' + own['project'] + '/plan-imports/' + foreign['import_job']['id'], status=404)
            self.call(own, own['import_path'] + '/source', token=foreign['token'], status=401)
        context = multiprocessing.get_context('spawn')
        for index, own in enumerate(self.companies):
            results = context.Queue()
            # PG fixture state includes a local binder closure; only the actual
            # worker configuration belongs in a spawned process, never API tokens.
            keys = ('instance_id', 'host', 'dsn', 'company', 'privacy') if 'dsn' in own else ('instance_id', 'host', 'database')
            worker_value = {key: own[key] for key in keys}
            worker = context.Process(target=process_company_import, args=(worker_value, results))
            worker.start()
            self.processes.append(worker)
            completed = results.get(timeout=60)
            worker.join(timeout=5)
            self.assertEqual(worker.exitcode, 0)
            self.assertNotEqual(completed['pid'], own['pid'])
            self.assertNotEqual(completed['pid'], os.getpid())
            self.assertEqual(completed['result']['id'], own['import_job']['id'])
            self.assertEqual(completed['result']['status'], 'needs_review')
            result = self.call(own, own['import_path'] + '/result')
            self.assertEqual(result['source']['sha256'], hashlib.sha256(own['import_bytes']).hexdigest())
            self.assertEqual(self.call(own, own['import_path'] + '/source', raw=True), own['import_bytes'])
            if index == 0:
                foreign = self.companies[1]
                self.assertEqual(self.call(foreign, foreign['import_path'])['status'], 'queued')
                self.call(foreign, foreign['import_path'] + '/result', status=409)


class CompanyIsolationCurrentHTTP(CurrentCompanyScenario, unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='synthetic-current-companies-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.companies = []
        self.processes = []
        self.addCleanup(self.stop)
        context = multiprocessing.get_context('spawn')
        for label in ('alpha', 'beta'):
            value = dict(database=str(self.root / (label + '.sqlite3')), host=label + '.example.test',
                instance_id=uuid.uuid4().hex, key=Fernet.generate_key(), storage=str(self.root / label), marker='ONLY' + label.upper())
            office = Office(value['database'])
            try:
                office.db.executescript(MFA_SCHEMA)
                office.add_user('same-owner@example.test', PASSWORD, 'owner')
                bind(office, value['instance_id'], value['host'], value['key'],
                    Storage(office, value['key'], value['host'], config={'server': {'path': value['storage']}}))
            finally:
                office.db.close()
            ports = context.Queue()
            process = context.Process(target=serve_company, args=(value, ports))
            process.start()
            self.processes.append(process)
            value.update(ports.get(timeout=25))
            self.companies.append(value)

    def stop(self):
        for process in self.processes:
            if process.is_alive():
                process.terminate()
            process.join(timeout=5)

    def test_two_processes_original_bytes_current_search_and_complete_archives(self):
        self.current_originals_search_and_export()

    def test_two_processes_contexts_same_rule_ids_event_jobs_and_actual_actions(self):
        self.current_context_events_and_same_rule_ids()

    def test_two_processes_private_originals_and_fresh_download_permissions(self):
        self.current_private_originals_and_fresh_permissions()

    @unittest.skipUnless(PARSER_PYTHON, 'Set SMARTPLAN_TEST_PARSER_PYTHON for actual local parser acceptance')
    def test_two_processes_queue_and_separate_actual_parser_processes(self):
        self.current_queue_and_actual_parser_processes()


if __name__ == '__main__':
    unittest.main()
