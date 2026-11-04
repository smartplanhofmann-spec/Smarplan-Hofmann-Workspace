"""Real local HTTP catalog envelope limit and byte-exact original replay."""
import base64
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
import uuid

from core import Office
from onedrive import OneDrive
from server import make_handler


def request(**values):
    return dict(request_id=uuid.uuid4().hex, **values)


class CatalogImportLocalHTTP(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='synthetic-catalog-http-')
        self.addCleanup(temporary.cleanup)
        self.office = Office(Path(temporary.name) / 'office.db')
        self.addCleanup(self.office.db.close)
        self.office.add_user('catalog-local@example.test', 'Synthetic-local-catalog-password', 'owner')
        self.token = self.office.login('catalog-local@example.test', 'Synthetic-local-catalog-password')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.office, OneDrive(self.office)))
        worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        source = self.call('POST', '/api/business/adapters', request(name='Synthetic local catalog', profile='catalog_csv_v1', enabled=True), status=201)
        self.path = '/api/business/adapters/' + source['id']

    def call(self, method, path, body=None, *, status=200, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=15)
        try:
            encoded = json.dumps(body).encode() if body is not None else None
            connection.request(method, path, encoded, dict({'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'}, **(headers or {})))
            response = connection.getresponse()
            raw = response.read()
            self.assertEqual(response.status, status, raw[:300])
            return json.loads(raw) if response.getheader('Content-Type', '').startswith('application/json') else raw
        finally:
            connection.close()

    def test_two_mib_original_uses_bounded_envelope_downloads_exactly_and_replays_once(self):
        row = b'code;name;unit;cost_price_net;unit_price_net;tax_rate\nSYN-HTTP;Synthetic switch;ST;1;2;19\n'
        raw = row + b'\n' * (2097152 - len(row))
        body = request(filename='Maximum.csv', content_base64=base64.b64encode(raw).decode())
        staged = self.call('POST', self.path + '/import', body, status=201)
        self.assertEqual(self.call('POST', self.path + '/import', body, status=201), staged)
        self.assertEqual(staged['original']['size'], 2097152)
        self.assertEqual(self.call('GET', '/api/business/adapters/imports/' + staged['id'] + '/original'), raw)
        self.assertEqual(self.call('GET', self.path + '/imports')['total'], 1)

    def test_decoded_size_envelope_other_route_and_strict_framing_reject_without_runs(self):
        self.call('POST', self.path + '/import', request(content_base64=base64.b64encode(b'x' * 2097153).decode()), status=413)
        self.call('POST', self.path + '/import', {}, status=413, headers={'Content-Length': '2850001'})
        self.call('POST', '/api/business/adapters', {}, status=413, headers={'Content-Length': '1000001'})
        self.call('GET', self.path + '/imports', {}, status=400)
        self.call('POST', self.path + '/import?ignored=1', {}, status=400)
        self.call('GET', self.path + '/imports?limit=1&limit=2', status=400)
        self.call('GET', self.path + '/imports?ignored=1', status=400)
        self.assertEqual(self.call('GET', self.path + '/imports')['total'], 0)


if __name__ == '__main__':
    unittest.main()
