"""Exercise the real pinned Caddy binary locally, with a trusted test-only CA.

Usage: SMARTPLAN_CADDY_BINARY=/tmp/.../caddy python3 deploy/hetzner/https/test_https.py
No ACME requests, external listeners, app data or system trust-store changes.
"""
import http.client
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import tempfile
import time
import unittest


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


class HttpsSetupTest(unittest.TestCase):
    def test_real_tls_redirect_and_application_isolation(self):
        self.assertNotEqual(os.geteuid(), 0, 'Run the smoke test without root.')
        binary = str(Path(os.environ['SMARTPLAN_CADDY_BINARY']).resolve(strict=True))
        source = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory(prefix='smartplan-https-') as temporary:
            root = Path(temporary)
            secure_port, plain_port = free_port(), free_port()
            while plain_port == secure_port:
                plain_port = free_port()
            # Only these local test overrides differ from the deployed configuration.
            config = (source / 'Caddyfile').read_text().replace(
                'office.smartplan-hofmann.de', f'localhost:{secure_port}'
            ).replace('/run/smartplan-https/admin.sock', str(root / 'admin.sock')).replace(
                '/usr/share/smartplan-setup', str(source)
            ).replace('{\n', '{\n\tskip_install_trust\n'
                      f'\thttp_port {plain_port}\n', 1)
            config = config.replace(f'localhost:{secure_port} {{',
                                    f'localhost:{secure_port} {{\n\tbind 127.0.0.1\n\ttls internal')
            config_path = root / 'Caddyfile'
            config_path.write_text(config)
            environment = dict(os.environ, XDG_DATA_HOME=str(root / 'state'),
                               XDG_CONFIG_HOME=str(root / 'config'))
            with (root / 'caddy.log').open('w+') as log:
                process = subprocess.Popen([binary, 'run', '--config', str(config_path),
                                            '--adapter', 'caddyfile'], env=environment,
                                           stdout=log, stderr=log)
                try:
                    certificate = root / 'state/caddy/pki/authorities/local/root.crt'
                    deadline = time.monotonic() + 20
                    while not certificate.exists():
                        if process.poll() is not None or time.monotonic() >= deadline:
                            log.seek(0)
                            self.fail(log.read())
                        time.sleep(.1)
                    trusted = ssl.create_default_context(cafile=str(certificate))

                    def request(path, method='GET', context=trusted):
                        connection = http.client.HTTPSConnection('localhost', secure_port,
                                                                 context=context, timeout=3)
                        try:
                            connection.request(method, path)
                            response = connection.getresponse()
                            return response.status, dict(response.getheaders()), response.read()
                        finally:
                            connection.close()

                    # A successful TLS request must actually validate the certificate.
                    while True:
                        try:
                            status, headers, body = request('/')
                            break
                        except (ConnectionRefusedError, ssl.SSLError):
                            if process.poll() is not None or time.monotonic() >= deadline:
                                log.seek(0)
                                self.fail(log.read())
                            time.sleep(.1)
                    self.assertEqual(status, 200)
                    self.assertIn('Onlinezugang wird vorbereitet'.encode(), body)
                    self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
                    self.assertIn("default-src 'none'", headers['Content-Security-Policy'])
                    self.assertNotIn('Server', headers)
                    self.assertEqual(request('/style.css')[0], 200)
                    self.assertEqual(request('/.git/config')[0], 404)
                    self.assertEqual(request('/backups/pilot.sqlite3')[0], 404)
                    for path in ('/api', '/api/projects', '/auth/login', '/oauth/callback', '/health', '/ready'):
                        for method in ('GET', 'POST'):
                            with self.subTest(path=path, method=method):
                                status, _, body = request(path, method)
                                self.assertEqual(status, 503)
                                self.assertEqual(json.loads(body), {'status': 'setup'})
                    with self.assertRaises(ssl.SSLCertVerificationError):
                        request('/', context=ssl.create_default_context())
                    connection = http.client.HTTPConnection('localhost', plain_port, timeout=3)
                    try:
                        connection.request('GET', '/', headers={'Host': 'localhost'})
                        response = connection.getresponse()
                        self.assertEqual(response.status, 308)
                        self.assertEqual(response.getheader('Location'), f'https://localhost:{secure_port}/')
                        response.read()
                    finally:
                        connection.close()
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
