"""Real authenticated Flask uploads and DB leases, with synthetic sources only."""
import base64
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from cryptography.fernet import Fernet
from PIL import Image
from reportlab.pdfgen import canvas

from core import Office
from online.web import create_app
from online.plan_imports import CHUNK_SIZE, PlanImports, LeaseLost, validate_integrity
from online.import_worker import work_one, main as worker_main


def sha(data):
    return hashlib.sha256(data).hexdigest()


def png():
    output = io.BytesIO()
    Image.new('RGB', (32, 24), 'white').save(output, format='PNG')
    return output.getvalue()


class PlanImportApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='smartplan-api-import-')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.database = self.directory / 'office.db'
        self.office = Office(self.database)
        self.key = Fernet.generate_key()
        self.owner_id = self.office.add_user('owner@example.test', 'Owner-password-123', 'owner')
        self.token = self.office.login('owner@example.test', 'Owner-password-123')
        self.owner = self.office.user(self.token)
        self.project = self.office.add_project(self.owner, 'Synthetic plan source', 'Fictional customer')
        self.open_app()

    def tearDown(self):
        self.office.db.close()

    def open_app(self):
        self.app = create_app(office=self.office, key=self.key, host='office.example.test')
        self.client = self.app.test_client()
        self.base = '/projects/' + self.project + '/plan-imports'

    def call(self, method, path, body=None, *, token='owner', status=200, mime=None, headers=None):
        token = self.token if token == 'owner' else token
        request_headers = {'Authorization': 'Bearer ' + token} if token else {}
        request_headers.update(headers or {})
        kwargs = {'json': body} if isinstance(body, dict) else {'data': body}
        response = self.client.open('/api/v1' + path, method=method, base_url='https://office.example.test',
                                    headers=request_headers, content_type=mime, **kwargs)
        self.assertEqual(response.status_code, status, repr(response.data[:500]))
        return response

    def manifest(self, data, **changes):
        return {'request_id': 'a' * 32, 'filename': 'paper-plan.png', 'media_type': 'image/png',
                'size': len(data), 'sha256': sha(data), 'page': 0, 'title': 'Ground floor', **changes}

    def upload(self, data=None, **manifest):
        data = data if data is not None else png()
        job = self.call('POST', self.base, self.manifest(data, **manifest), status=201).json
        path = self.base + '/' + job['id']
        for index, start in enumerate(range(0, len(data), CHUNK_SIZE)):
            self.call('PUT', path + '/chunks/' + str(index), data[start:start + CHUNK_SIZE], mime='application/octet-stream')
        queued = self.call('POST', path + '/complete', {}).json
        return path, queued

    def publish(self, import_id, *, clock=time.time):
        imports = PlanImports(self.office, clock=clock)
        with self.office.lock, self.office.db:
            claim = imports.claim(lease_seconds=5)
            self.assertEqual(claim['id'], import_id)
            result = {'schema_version': 1, 'status': 'needs_review',
                      'source': {'sha256': claim['sha256'], 'selected_page': claim['page']},
                      'analysis': {'line_candidates': [], 'text_candidates': []}}
            return imports.publish(import_id, claim['lease_token'], preview=png(), result=result)

    def test_interrupted_chunks_resume_after_restart_without_replacing_original(self):
        data = b'Synthetic original bytes:' + b'z' * (CHUNK_SIZE + 30)
        manifest = self.manifest(data)
        created = self.call('POST', self.base, manifest, status=201).json
        path = self.base + '/' + created['id']
        self.call('PUT', path + '/chunks/0', data[:CHUNK_SIZE], mime='application/octet-stream')
        self.call('POST', path + '/complete', {}, status=409)
        self.call('GET', path + '/source', status=409)
        self.office.db.close()
        self.office = Office(self.database)
        self.open_app()
        resumed = self.call('POST', self.base, manifest, status=201).json
        self.assertEqual(resumed['id'], created['id'])
        self.assertEqual(resumed['uploaded_chunks'], [0])
        self.call('PUT', path + '/chunks/0', data[:CHUNK_SIZE], mime='application/octet-stream')
        self.call('PUT', path + '/chunks/0', b'!' + data[1:CHUNK_SIZE], mime='application/octet-stream', status=409)
        self.call('PUT', path + '/chunks/1', data[CHUNK_SIZE:], mime='application/octet-stream')
        self.assertEqual(self.call('POST', path + '/complete', {}).json['status'], 'queued')
        self.assertEqual(self.call('POST', path + '/complete', {}).json['status'], 'queued')
        self.assertEqual(self.call('GET', path + '/source').data, data)
        self.call('POST', self.base, {**manifest, 'title': 'Changed'}, status=409)
        self.assertEqual(self.call('GET', self.base).json[0]['id'], created['id'])
        self.assertTrue(validate_integrity(self.office))

    def test_complete_checks_full_hash_and_never_confirms_partial_or_wrong_source(self):
        data = png()
        job = self.call('POST', self.base, self.manifest(data, sha256='0' * 64), status=201).json
        path = self.base + '/' + job['id']
        self.call('PUT', path + '/chunks/0', data, mime='application/octet-stream')
        self.call('POST', path + '/complete', {}, status=409)
        self.assertEqual(self.call('GET', path).json['status'], 'uploading')
        self.call('GET', path + '/source', status=409)
        self.assertIsNone(PlanImports(self.office).claim())

    def test_auth_scope_roles_and_fresh_offline_credential_project_checks(self):
        path, job = self.upload()
        tech_id = self.office.add_user('tech@example.test', 'Technician-password-123', 'technician')
        tech = self.office.login('tech@example.test', 'Technician-password-123')
        self.call('GET', path, token=None, status=401)
        self.call('GET', path, token=tech, status=404)
        self.office.assign(self.owner, self.project, tech_id)
        offline = self.call('POST', '/offline/access', {}, token=tech, status=201).json['token']
        self.call('GET', path + '/source', token=offline)
        self.call('GET', '/users', token=offline, status=403)
        self.call('POST', self.base, self.manifest(png(), request_id='c' * 32), token=offline, status=201)
        self.office.assign(self.owner, self.project, tech_id, remove=True)
        self.call('GET', path + '/source', token=offline, status=404)
        self.office.assign(self.owner, self.project, tech_id)
        with self.office.db:
            self.office.db.execute('UPDATE users SET password=? WHERE id=?', ('changed', tech_id))
        self.call('GET', path, token=offline, status=401)
        accountant_id = self.office.add_user('accounts@example.test', 'Accountant-password-123', 'accountant')
        accountant = self.office.login('accounts@example.test', 'Accountant-password-123')
        self.office.assign(self.owner, self.project, accountant_id)
        self.call('GET', path, token=accountant)
        self.call('GET', path + '/source', token=accountant)
        self.call('POST', path + '/complete', {}, token=accountant, status=403)
        other = self.office.add_project(self.owner, 'Other', 'Other customer')
        self.call('GET', '/projects/' + other + '/plan-imports/' + job['id'], status=404)

    def test_binary_endpoint_limit_is_local_and_manifest_lengths_are_exact(self):
        job = self.call('POST', self.base, self.manifest(png()), status=201).json
        chunk = self.base + '/' + job['id'] + '/chunks/0'
        self.call('PUT', chunk, b'x' * (CHUNK_SIZE + 1), mime='application/octet-stream', status=413)
        self.call('PUT', chunk, b'x', mime='application/octet-stream', status=400)
        self.call('PUT', chunk, b'x', mime='application/json', status=415)
        self.call('PUT', chunk, png(), mime='application/octet-stream', headers={'Content-Encoding': 'gzip'}, status=400)
        self.call('POST', self.base, {'payload': 'x' * 1_000_000}, status=413)
        self.assertEqual(self.app.config['MAX_CONTENT_LENGTH'], 1_000_000)

    def test_lost_lease_cannot_publish_and_review_artifacts_have_verified_hashes(self):
        path, job = self.upload()
        now = [1000.0]
        imports = PlanImports(self.office, clock=lambda: now[0])
        with self.office.lock, self.office.db:
            first = imports.claim(lease_seconds=5)
        now[0] += 6
        with self.office.lock, self.office.db:
            second = imports.claim(lease_seconds=5)
            with self.assertRaises(LeaseLost):
                imports.fail(job['id'], first['lease_token'])
            result = {'schema_version': 1, 'status': 'needs_review',
                      'source': {'sha256': job['sha256'], 'selected_page': job['page']}}
            with self.assertRaises(LeaseLost):
                imports.publish(job['id'], first['lease_token'], preview=png(), result=result)
            imports.publish(job['id'], second['lease_token'], preview=png(), result=result)
        status = self.call('GET', path).json
        self.assertEqual(status['status'], 'needs_review')
        self.assertEqual(status['preview_sha256'], sha(png()))
        self.assertEqual(status['preview_size'], len(png()))
        self.assertNotIn('lease_token', status)
        self.assertEqual(self.call('GET', path + '/preview').data, png())
        self.assertEqual(self.call('GET', path + '/result').json, result)
        self.assertEqual(self.call('GET', path + '/source').data, png())
        self.assertTrue(validate_integrity(self.office))

    def test_three_abandoned_attempts_fail_and_preserve_original(self):
        path, job = self.upload()
        now = [1000.0]
        imports = PlanImports(self.office, clock=lambda: now[0])
        for attempt in range(1, 4):
            with self.office.lock, self.office.db:
                claimed = imports.claim(lease_seconds=5)
            self.assertEqual(claimed['attempts'], attempt)
            now[0] += 6
        with self.office.lock, self.office.db:
            self.assertIsNone(imports.claim())
        status = self.call('GET', path).json
        self.assertEqual((status['status'], status['error_code']), ('failed', 'attempts_exhausted'))
        self.assertEqual(self.call('GET', path + '/source').data, png())
        self.assertTrue(validate_integrity(self.office))

    def test_integrity_rejects_wrong_semantic_source_even_with_updated_artifact_hash(self):
        _, job = self.upload()
        self.publish(job['id'])
        changed = json.dumps({'schema_version': 1, 'status': 'needs_review',
                              'source': {'sha256': '0' * 64, 'selected_page': job['page']}})
        with self.office.db:
            self.office.db.execute('UPDATE plan_imports SET result=?,result_sha256=? WHERE id=?',
                                   (changed, sha(changed.encode()), job['id']))
        with self.assertRaises(ValueError):
            validate_integrity(self.office)

    def test_same_pdf_hash_cannot_publish_or_restore_a_different_page_or_schema(self):
        document = io.BytesIO()
        pdf = canvas.Canvas(document, invariant=1)
        for page in (1, 2):
            pdf.drawString(72, 720, 'Synthetic page ' + str(page))
            pdf.showPage()
        pdf.save()
        _, job = self.upload(document.getvalue(), media_type='application/pdf', filename='two-pages.pdf', page=1)
        imports = PlanImports(self.office)
        with self.office.lock, self.office.db:
            claimed = imports.claim(lease_seconds=5)
            valid = {'schema_version': 1, 'status': 'needs_review',
                     'source': {'sha256': job['sha256'], 'selected_page': 1}}
            invalid_results = [
                {**valid, 'source': {**valid['source'], 'selected_page': 0}},
                {**valid, 'source': {**valid['source'], 'selected_page': True}},
                {**valid, 'schema_version': True},
                {**valid, 'schema_version': 2},
            ]
            for invalid in invalid_results:
                with self.subTest(publish=invalid), self.assertRaises(ValueError):
                    imports.publish(job['id'], claimed['lease_token'], preview=png(), result=invalid)
            imports.publish(job['id'], claimed['lease_token'], preview=png(), result=valid)
        for invalid in invalid_results:
            encoded = json.dumps(invalid)
            with self.office.db:
                self.office.db.execute('UPDATE plan_imports SET result=?,result_sha256=? WHERE id=?',
                                       (encoded, sha(encoded.encode()), job['id']))
            with self.subTest(restore=invalid), self.assertRaises(ValueError):
                validate_integrity(self.office)

    def fake_worker(self, body):
        script = self.directory / 'synthetic worker ; no shell'
        script.write_text('#!' + sys.executable + '\nimport os,sys,json,hashlib,base64,subprocess,time\n'
                          'from pathlib import Path\n' + body)
        script.chmod(0o700)
        return script

    def test_unconfigured_or_invalid_cli_never_opens_database_or_claims_queued_source(self):
        path, _ = self.upload()
        invalid = self.directory / 'not-executable'
        invalid.write_text('synthetic non-executable configuration')
        invalid.chmod(0o600)
        environment = {key: value for key, value in os.environ.items()
                       if key not in ('SMARTPLAN_IMPORT_WORKER_PYTHON', 'SMARTPLAN_DATABASE_DSN')}
        for arguments in (['--once'], ['--once', '--worker-python', 'python'],
                          ['--once', '--worker-python', str(invalid)],
                          ['--once', '--worker-python', str(self.directory / 'missing')]):
            with self.subTest(arguments=arguments), patch.dict(os.environ, environment, clear=True):
                with patch('online.store.PostgresOffice') as database, redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as stopped:
                        worker_main(arguments)
                self.assertEqual(stopped.exception.code, 2)
                database.assert_not_called()
            job = self.call('GET', path).json
            self.assertEqual((job['status'], job['attempts']), ('queued', 0))
            self.assertEqual(self.call('GET', path + '/source').data, png())

    def test_configured_cli_reports_processing_failure_with_nonzero_exit(self):
        path, _ = self.upload()
        worker = self.fake_worker("print(json.dumps({'status':'failed','error_code':'recognizer_unavailable'}))\nsys.exit(1)\n")
        output = io.StringIO()
        with patch.dict(os.environ, {'SMARTPLAN_DATABASE_DSN': 'synthetic-not-a-real-dsn',
                                     'SMARTPLAN_IMPORT_WORKER_PYTHON': str(worker)}):
            with patch('online.store.PostgresOffice', return_value=self.office) as database, \
                    patch('online.import_worker.signal.signal'), redirect_stdout(output):
                exit_code = worker_main(['--once'])
                database.assert_called_once_with('synthetic-not-a-real-dsn')
        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(output.getvalue())['status'], 'failed')
        # The CLI owns/closes its connection; reopening models another process.
        self.office = Office(self.database)
        self.open_app()
        status = self.call('GET', path).json
        self.assertEqual((status['status'], status['error_code']), ('failed', 'recognizer_unavailable'))
        self.assertEqual(self.call('GET', path + '/source').data, png())
        self.assertTrue(validate_integrity(self.office))

    def test_supervised_worker_publishes_database_results_without_inherited_secrets(self):
        path, job = self.upload()
        body = ("assert not any(name in os.environ for name in ('SMARTPLAN_DATABASE_DSN','SMARTPLAN_VAULT_KEY_FILE','HTTP_PROXY','PRIVATE_CANARY'))\n"
                "args=sys.argv\nsource=Path(args[args.index('--source')+1]).read_bytes()\n"
                "stage=Path(args[args.index('--output')+1])\n"
                "(stage/'preview.png').write_bytes(base64.b64decode(" + repr(base64.b64encode(png()).decode()) + "))\n"
                "(stage/'result.json').write_text(json.dumps({'schema_version':1,'status':'needs_review','source':{'sha256':hashlib.sha256(source).hexdigest(),'selected_page':int(args[args.index('--page')+1])}}))\n"
                "print(json.dumps({'status':'needs_review'}))\n")
        with patch.dict(os.environ, {'SMARTPLAN_DATABASE_DSN': 'synthetic-private', 'SMARTPLAN_VAULT_KEY_FILE': 'synthetic-private',
                                     'HTTP_PROXY': 'synthetic-private', 'PRIVATE_CANARY': 'must-not-be-inherited'}):
            result = work_one(self.office, worker_python=self.fake_worker(body))
        self.assertEqual(result['status'], 'needs_review')
        self.assertEqual(self.call('GET', path + '/preview').data, png())
        self.assertEqual(self.call('GET', path + '/source').data, png())
        self.assertTrue(validate_integrity(self.office))

    def test_worker_timeout_stops_descendants_and_keeps_database_original(self):
        path, _ = self.upload()
        escaped = self.directory / 'worker-descendant-escaped'
        child = ('import time; from pathlib import Path; time.sleep(1.5); Path('
                 + repr(str(escaped)) + ').write_text("escaped")')
        worker = self.fake_worker('subprocess.Popen([sys.executable,"-c",' + repr(child) + '])\ntime.sleep(30)\n')
        result = work_one(self.office, worker_python=worker, process_timeout=1)
        self.assertEqual((result['status'], result['error_code']), ('failed', 'processing_timeout'))
        self.assertEqual(self.call('GET', path + '/source').data, png())
        time.sleep(1.8)
        self.assertFalse(escaped.exists())
        self.assertTrue(validate_integrity(self.office))

    def test_fifo_worker_artifacts_fail_without_blocking_or_losing_the_original(self):
        controller = (
            'import json,sys; from core import Office; from online.import_worker import work_one; '
            'office=Office(sys.argv[1]); '
            'result=work_one(office,worker_python=sys.argv[2]); '
            'print(json.dumps({"status":result["status"],"error_code":result["error_code"]})); '
            'office.db.close()')
        for kind, request_id in (('preview.png', 'b' * 32), ('result.json', 'c' * 32)):
            with self.subTest(fifo=kind):
                path, _ = self.upload(request_id=request_id)
                body = "args=sys.argv\nstage=Path(args[args.index('--output')+1])\n"
                if kind == 'preview.png':
                    body += "os.mkfifo(stage/'preview.png',0o600)\n(stage/'result.json').write_text('{}')\n"
                else:
                    body += "(stage/'preview.png').write_bytes(base64.b64decode(" + repr(base64.b64encode(png()).decode()) + "))\n"
                    body += "os.mkfifo(stage/'result.json',0o600)\n"
                worker = self.fake_worker(body + "print(json.dumps({'status':'needs_review'}))\n")
                environment = {**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1])}
                completed = subprocess.run([sys.executable, '-c', controller, str(self.database), str(worker)],
                                           capture_output=True, text=True, timeout=6, env=environment)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertEqual(json.loads(completed.stdout), {'status': 'failed', 'error_code': 'processing_failed'})
                self.assertEqual(self.call('GET', path + '/source').data, png())
                self.assertTrue(validate_integrity(self.office))


# PostgreSQL cases reuse the real MFA fixtures, on an explicitly disposable DB.
import test_online as postgres_fixtures
from online.store import PostgresOffice


@unittest.skipUnless(postgres_fixtures.DSN, 'Disposable SMARTPLAN_TEST_DSN required')
class PostgresImportTests(unittest.TestCase):
    setUp = postgres_fixtures.OnlineApiTests.setUp
    tearDown = postgres_fixtures.OnlineApiTests.tearDown
    request = postgres_fixtures.OnlineApiTests.request
    login = postgres_fixtures.OnlineApiTests.login

    def test_mfa_binary_source_survives_new_database_connection(self):
        token = self.login()['token']
        project = self.request('/projects', {'name': 'Import', 'customer': 'Synthetic'}, token, 201).json['id']
        base = '/projects/' + project + '/plan-imports'
        source = png()
        manifest = {'request_id': 'f' * 32, 'filename': 'source.png', 'media_type': 'image/png',
                    'size': len(source), 'sha256': sha(source), 'page': 0, 'title': 'Photo'}
        job = self.request(base, manifest, token, 201).json
        path = base + '/' + job['id']
        response = self.client.put('/api/v1' + path + '/chunks/0', data=source, content_type='application/octet-stream',
                                   base_url='https://office.example.test', headers={'Authorization': 'Bearer ' + token})
        self.assertEqual(response.status_code, 200, response.data)
        self.request(path + '/complete', {}, token)
        self.office.db.close()
        self.office = PostgresOffice(postgres_fixtures.DSN)
        self.client = create_app(office=self.office, key=self.key, host='office.example.test').test_client()
        self.assertEqual(self.request(path + '/source', token=token).data, source)
        self.assertTrue(validate_integrity(self.office))

    def test_claims_from_separate_connections_cannot_both_own_one_job(self):
        from concurrent.futures import ThreadPoolExecutor
        token = self.login()['token']
        project = self.request('/projects', {'name': 'Import', 'customer': 'Synthetic'}, token, 201).json['id']
        imports = PlanImports(self.office)
        with self.office.lock, self.office.db:
            actor = self.office.user(token)
            source = png()
            job = imports.create(actor, project, {'request_id': 'e' * 32, 'filename': 'source.png', 'media_type': 'image/png',
                      'size': len(source), 'sha256': sha(source), 'page': 0, 'title': 'Photo'})
            imports.put_chunk(actor, project, job['id'], 0, source)
            imports.complete_upload(actor, project, job['id'])
        def claim(_):
            office = PostgresOffice(postgres_fixtures.DSN)
            try:
                with office.lock, office.db:
                    return PlanImports(office).claim()
            finally:
                office.db.close()
        with ThreadPoolExecutor(max_workers=2) as executor:
            claims = list(executor.map(claim, range(2)))
        self.assertEqual(sum(value is not None for value in claims), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
