"""Real Caddy TLS -> two Gunicorn workers -> PostgreSQL -> signed PDF, then restart."""
import http.client
import configparser
import json
import os
from pathlib import Path
import socket
import shlex
import ssl
import subprocess
import sys
import tempfile
import time
import unittest

from cryptography.fernet import Fernet
from psycopg.conninfo import conninfo_to_dict
from online.auth import totp
from online.store import migrate, PostgresOffice


def port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def stop(process):
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


class RuntimeTest(unittest.TestCase):
    def test_https_mfa_pdf_and_worker_restart(self):
        self.assertNotEqual(os.geteuid(), 0)
        dsn = os.environ['SMARTPLAN_TEST_DSN']
        self.assertEqual(conninfo_to_dict(dsn).get('dbname'), 'smartplan_check', 'Disposable test database required.')
        migrate(dsn)
        office = PostgresOffice(dsn)
        # This fixture uses a new vault key. Isolate it from storage/OAuth
        # records encrypted by the preceding disposable-database test suites.
        with office.lock, office.db:
            office.db.execute('TRUNCATE users,customers,projects,assignments,reports,audit,secrets,'
                              'sessions,mfa,auth_challenges,login_limits RESTART IDENTITY CASCADE')
        email = 'runtime-' + str(time.time_ns()) + '@example.test'
        office.add_user(email, 'Runtime-test-password-123', 'owner')
        office.db.close()
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory(prefix='smartplan-runtime-') as temporary:
            temporary = Path(temporary)
            ports = set()
            while len(ports) < 3:
                ports.add(port())
            api_port, tls_port, http_port = ports
            keyfile = temporary / 'vault.key'
            keyfile.write_bytes(Fernet.generate_key())
            keyfile.chmod(0o400)
            storage_config = temporary / 'storage.json'
            storage_config.write_text(json.dumps({'server': {'path': str(temporary / 'documents')}}))
            storage_config.chmod(0o600)
            environment = dict(os.environ, SMARTPLAN_DATABASE_DSN=dsn,
                SMARTPLAN_PUBLIC_HOST='office.example.test', SMARTPLAN_VAULT_KEY_FILE=str(keyfile),
                SMARTPLAN_STORAGE_CONFIG_FILE=str(storage_config))
            unit = configparser.ConfigParser(interpolation=None)
            unit.read(root / 'deploy/hetzner/online/smartplan-online.service')
            command = [sys.executable, '-m', 'gunicorn', *shlex.split(unit['Service']['ExecStart'])[2:]]
            command[command.index('--bind') + 1] = f'127.0.0.1:{api_port}'
            config = (root / 'deploy/hetzner/online/Caddyfile').read_text()
            config = config.replace('office.smartplan-hofmann.de', f'localhost:{tls_port}').replace(
                '/run/smartplan-https/admin.sock', str(temporary / 'admin.sock')).replace(
                '/usr/share/smartplan-setup', str(root / 'deploy/hetzner/https')).replace(
                '127.0.0.1:8766 {', f'127.0.0.1:{api_port} {{\n\t\t\theader_up Host office.example.test')
            config = config.replace('{\n', f'{{\n\tskip_install_trust\n\thttp_port {http_port}\n', 1)
            config = config.replace(f'localhost:{tls_port} {{', f'localhost:{tls_port} {{\n\tbind 127.0.0.1\n\ttls internal')
            configfile = temporary / 'Caddyfile'
            configfile.write_text(config)
            with (temporary / 'runtime.log').open('w+') as log:
                worker = subprocess.Popen(command, cwd=root / 'backend', env=environment, stdout=log, stderr=log)
                try:
                    caddy = subprocess.Popen([os.environ['SMARTPLAN_CADDY_BINARY'], 'run', '--config', str(configfile),
                                              '--adapter', 'caddyfile'], stdout=log, stderr=log,
                        env=dict(os.environ, XDG_DATA_HOME=str(temporary / 'state'), XDG_CONFIG_HOME=str(temporary / 'config')))
                except BaseException:
                    stop(worker)
                    raise
                try:
                    certificate = temporary / 'state/caddy/pki/authorities/local/root.crt'
                    deadline = time.monotonic() + 20
                    while not certificate.exists():
                        if time.monotonic() > deadline or caddy.poll() is not None:
                            log.seek(0)
                            self.fail(log.read())
                        time.sleep(.1)
                    trusted = ssl.create_default_context(cafile=str(certificate))

                    def request(path, data=None, token=None, expected=200):
                        connection = http.client.HTTPSConnection('localhost', tls_port, context=trusted, timeout=5)
                        headers = {'Content-Type': 'application/json'}
                        if token:
                            headers['Authorization'] = 'Bearer ' + token
                        try:
                            connection.request('POST' if data is not None else 'GET', path,
                                               body=json.dumps(data) if data is not None else None, headers=headers)
                            response = connection.getresponse()
                            payload = response.read()
                            self.assertEqual(response.status, expected, repr(payload[:200]))
                            return payload
                        finally:
                            connection.close()

                    while True:
                        try:
                            health = json.loads(request('/ready'))
                            self.assertEqual(health['database'], 'ok')
                            break
                        except (AssertionError, OSError):
                            if time.monotonic() > deadline or worker.poll() is not None:
                                log.seek(0)
                                self.fail(log.read())
                            time.sleep(.1)
                    request('/api/v1/projects', expected=401)
                    pending = json.loads(request('/api/v1/login', {'email': email, 'password': 'Runtime-test-password-123'}))
                    result = json.loads(request('/api/v1/login/verify', {'challenge': pending['challenge'],
                        'code': totp(pending['enrollment']['secret'], int(time.time() // 30))}))
                    token = result['token']
                    project = json.loads(request('/api/v1/projects', {'name': 'Runtime-Test', 'customer': 'Testkunde'}, token, 201))['id']
                    report = json.loads(request(f'/api/v1/projects/{project}/reports',
                        {'kind': 'Servicebericht', 'description': 'Fiktive Runtime-Prüfung'}, token, 201))
                    request(f"/api/v1/reports/{report['id']}/sign", {'content_hash': report['content_hash'],
                        'signer': 'Testkunde', 'strokes': [[[0.1, 0.2], [0.7, 0.8]]]}, token)
                    pdf = request(f"/api/v1/reports/{report['id']}/pdf", token=token)
                    self.assertTrue(pdf.startswith(b'%PDF'))
                    storage = json.loads(request('/api/v1/storage/status', token=token))
                    self.assertEqual(storage['selected_provider'], 'none')
                    self.assertTrue(next(p for p in storage['providers'] if p['id'] == 'server')['configured'])
                    request('/api/v1/storage/provider', {'provider': 'server'}, token)
                    uploaded = json.loads(request(f"/api/v1/reports/{report['id']}/storage", {}, token))
                    self.assertEqual(uploaded, {'uploaded': True, 'provider': 'server'})
                    saved = temporary / 'documents' / project / (report['id'] + '.pdf')
                    self.assertEqual(saved.read_bytes(), pdf)
                    stop(worker)
                    worker = subprocess.Popen(command, cwd=root / 'backend', env=environment, stdout=log, stderr=log)
                    deadline = time.monotonic() + 15
                    while True:
                        try:
                            request('/ready')
                            break
                        except (AssertionError, OSError):
                            if time.monotonic() > deadline:
                                raise
                            time.sleep(.1)
                    self.assertEqual(pdf, request(f"/api/v1/reports/{report['id']}/pdf", token=token))
                    self.assertEqual(json.loads(request('/api/v1/storage/status', token=token))['selected_provider'], 'server')
                    self.assertEqual(saved.read_bytes(), pdf)
                    request('/api/projects', expected=503)
                finally:
                    stop(caddy)
                    stop(worker)


if __name__ == '__main__':
    unittest.main(verbosity=2)
