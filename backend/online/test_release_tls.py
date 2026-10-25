"""Real, verified loopback TLS for the update maintenance gate.

Requires SMARTPLAN_CADDY_BINARY. No PostgreSQL, ACME, public listeners or system
trust-store changes are used. The upstream is synthetic and only returns 401.
"""
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest

from online.release import maintenance_config


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


def stop(process):
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


@unittest.skipUnless(os.environ.get('SMARTPLAN_CADDY_BINARY'), 'Pinned SMARTPLAN_CADDY_BINARY required')
class ReleaseMaintenanceTlsTest(unittest.TestCase):
    def test_real_restart_gates_get_and_post_then_reload_restores_upstream(self):
        self.assertNotEqual(os.geteuid(), 0, 'Run this local TLS test without root.')
        binary = str(Path(os.environ['SMARTPLAN_CADDY_BINARY']).resolve(strict=True))
        repository = Path(__file__).resolve().parents[2]
        seen, lock = [], threading.Lock()

        class Upstream(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'

            def handle_request(self):
                length = int(self.headers.get('Content-Length', '0'))
                if length:
                    self.rfile.read(length)
                with lock:
                    seen.append((self.command, self.path))
                body = b'{"error":"Synthetic upstream requires authentication"}'
                self.send_response(401)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Security-Policy', "default-src 'none'")
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            do_GET = handle_request
            do_POST = handle_request
            do_PUT = handle_request

            def log_message(self, format, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Upstream)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        process = None
        try:
            with tempfile.TemporaryDirectory(prefix='smartplan-release-tls-') as temporary:
                try:
                    root = Path(temporary)
                    tls_port = free_port()
                    while tls_port == server.server_port:
                        tls_port = free_port()
                    admin = root / 'admin.sock'
                    online = (repository / 'deploy/hetzner/online/Caddyfile').read_text()
                    # The deployed handler is unchanged. Only listener, certificate,
                    # state and synthetic-upstream destinations are local test overrides.
                    online = online.replace('office.smartplan-hofmann.de', f'localhost:{tls_port}').replace(
                        '/run/smartplan-https/admin.sock', str(admin)).replace(
                        '/usr/share/smartplan-setup', str(repository / 'deploy/hetzner/https')).replace(
                        '127.0.0.1:8766', f'127.0.0.1:{server.server_port}')
                    online = online.replace('{\n', '{\n\tskip_install_trust\n\tauto_https disable_redirects\n', 1)
                    online = online.replace(f'localhost:{tls_port} {{',
                                            f'localhost:{tls_port} {{\n\tbind 127.0.0.1\n\ttls internal', 1)
                    maintenance = maintenance_config(online)
                    config = root / 'Caddyfile'
                    config.write_text(online)
                    environment = dict(os.environ, XDG_DATA_HOME=str(root / 'state'),
                                       XDG_CONFIG_HOME=str(root / 'config'))
                    with (root / 'caddy.log').open('w+') as log:
                        def failure(message):
                            log.flush()
                            log.seek(0)
                            self.fail(message + '\n' + log.read()[-16000:])

                        def start():
                            return subprocess.Popen([binary, 'run', '--config', str(config), '--adapter', 'caddyfile'],
                                                    env=environment, stdout=log, stderr=log)

                        process = start()
                        certificate = root / 'state/caddy/pki/authorities/local/root.crt'
                        deadline = time.monotonic() + 20
                        while not certificate.exists():
                            if process.poll() is not None or time.monotonic() >= deadline:
                                failure('Caddy did not create its isolated test CA.')
                            time.sleep(.1)
                        trusted = ssl.create_default_context(cafile=str(certificate))

                        def request(path, method='GET', context=trusted):
                            connection = http.client.HTTPSConnection('localhost', tls_port, context=context, timeout=3)
                            try:
                                body = b'\x89PNG\r\n\x1a\n' if method == 'PUT' else '{}' if method == 'POST' else None
                                connection.request(method, path, body=body,
                                                   headers={'Content-Type': 'application/octet-stream' if method == 'PUT' else 'application/json'})
                                response = connection.getresponse()
                                return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read()
                            finally:
                                connection.close()

                        def wait_status(expected):
                            deadline = time.monotonic() + 15
                            while True:
                                try:
                                    result = request('/api/v1/projects')
                                    if result[0] == expected:
                                        return result
                                except (OSError, ssl.SSLError):
                                    pass
                                if process.poll() is not None or time.monotonic() >= deadline:
                                    failure('Caddy did not reach expected HTTP status ' + str(expected))
                                time.sleep(.1)

                        wait_status(401)
                        self.assertEqual(request('/api/v1/projects', 'POST')[0], 401)
                        self.assertEqual(request('/ready')[0], 401)
                        self.assertEqual(request('/api/v1/business/meta')[0], 401)
                        self.assertNotIn("script-src 'self'", request('/api/v1/projects')[1]['content-security-policy'])
                        for path in ('/', '/office', '/office/', '/office/office.js', '/office/contact.html', '/office/contact.js'):
                            with self.subTest(phase='browser', path=path):
                                status, headers, _ = request(path)
                                self.assertEqual(status, 401)
                                self.assertIn("script-src 'self'", headers['content-security-policy'])
                                self.assertIn("connect-src 'self'", headers['content-security-policy'])
                                self.assertNotIn("'unsafe-inline'", headers['content-security-policy'])
                        # Prove the test is using an explicitly trusted CA rather than
                        # accidentally accepting this certificate through global trust.
                        with self.assertRaises(ssl.SSLCertVerificationError):
                            request('/api/v1/projects', context=ssl.create_default_context())
                        old_process = process
                        stop(process)
                        self.assertIsNotNone(old_process.poll())
                        with lock:
                            before_maintenance = len(seen)
                        config.write_text(maintenance)
                        process = start()
                        self.assertNotEqual(old_process.pid, process.pid)
                        wait_status(503)
                        project = 'a' * 32
                        source = 'b' * 32
                        import_path = f'/api/v1/projects/{project}/plan-imports/{source}'
                        for path in ('/', '/office', '/office/office.js', '/office/contact.html', '/office/contact.js',
                                     '/api/v1/intake/contact', '/api/v1/business/meta', '/api/v1/business/documents/finalize',
                                     '/api/v1/projects', '/api/v1/offline/access', '/ready', '/health',
                                     import_path, import_path + '/source', import_path + '/preview',
                                     import_path + '/result', import_path + '/chunks/0'):
                            for method in ('GET', 'POST', 'PUT'):
                                with self.subTest(phase='maintenance', path=path, method=method):
                                    status, headers, body = request(path, method)
                                    self.assertEqual(status, 503)
                                    self.assertEqual(headers.get('retry-after'), '60')
                                    self.assertEqual(headers.get('cache-control'), 'no-store')
                                    self.assertIn('Serverupdate', json.loads(body)['error'])
                        with lock:
                            self.assertEqual(len(seen), before_maintenance,
                                             'A maintenance request reached the upstream.')
                        config.write_text(online)
                        reload = subprocess.run([binary, 'reload', '--config', str(config), '--adapter', 'caddyfile',
                                                 '--address', 'unix/' + str(admin)], env=environment,
                                                stdout=log, stderr=log, timeout=15)
                        if reload.returncode:
                            failure('Caddy rejected restoration of the original config.')
                        wait_status(401)
                        self.assertEqual(request('/api/v1/projects', 'POST')[0], 401)
                        self.assertEqual(request('/ready')[0], 401)
                        with lock:
                            self.assertGreater(len(seen), before_maintenance)

                finally:
                    stop(process)
                    process = None
        finally:
            stop(process)
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())


if __name__ == '__main__':
    unittest.main(verbosity=2)
