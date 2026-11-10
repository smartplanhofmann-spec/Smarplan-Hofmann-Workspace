"""Real local HTTP framing and narrow signed report device capabilities."""
from datetime import datetime, timedelta, timezone
import hashlib
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest
import uuid

from core import Office, canonical
from onedrive import OneDrive
import plan_access
from server import make_handler


class OfflineReportLocalTransportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix='synthetic-offline-report-local-')
        self.addCleanup(temp.cleanup)
        self.office = Office(Path(temp.name) / 'office.db')
        self.addCleanup(self.office.db.close)
        self.office.add_user('owner@example.test', 'Synthetic-password-123', 'owner')
        self.full = self.office.login('owner@example.test', 'Synthetic-password-123')
        actor = self.office.user(self.full)
        self.project = self.office.add_project(actor, 'Synthetic local site', 'Synthetic customer')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.office, OneDrive(self.office)))
        worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.token = self.call('POST', '/business/offline/access', {}, token=self.full, status=201)[0]['token']

    def call(self, method, path, body=None, *, token=None, status=200, headers=None):
        request_headers = {'Authorization': 'Bearer ' + (token or self.token), 'Content-Type': 'application/json'}
        request_headers.update(headers or {})
        raw = canonical(body).encode() if isinstance(body, dict) else body
        client = HTTPConnection('127.0.0.1', self.server.server_port, timeout=6)
        try:
            client.request(method, '/api' + path, body=raw, headers=request_headers)
            response = client.getresponse()
            content = response.read()
            self.assertEqual(response.status, status, (path, content[:400]))
            return (json.loads(content) if response.getheader('Content-Type', '').startswith('application/json') else content), response
        finally:
            client.close()

    def capture(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        body = dict(request_id=uuid.uuid4().hex, entry_id=uuid.uuid4().hex, project_id=self.project,
            content=dict(title=' Synthetisches Protokoll ', description='Gerät geprüft: Größe 3 m²', notes='',
                project_name='Synthetic local site', customer='Synthetic customer',
                captured_at=(now - timedelta(minutes=2)).isoformat()),
            signer='Synthetic customer', strokes=[[[0.1, 0.2], [0.5, 0.4]]],
            signed_at=(now - timedelta(minutes=1)).isoformat())
        body['content_hash'] = hashlib.sha256(canonical([body['entry_id'], self.project, body['content']]).encode()).hexdigest()
        return body

    def test_local_wire_signed_capture_replay_and_pdf_under_narrow_device_scope(self):
        body = self.capture()
        path = '/business/service-reports/offline'
        row = self.call('POST', path, body, status=201)[0]
        self.assertEqual(self.call('POST', path, body, status=201)[0], row)
        archive = '/business/service-reports/' + row['id']
        self.assertEqual(self.call('GET', archive)[0], row)
        pdf = self.call('GET', archive + '/pdf')[0]
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertEqual(hashlib.sha256(pdf).hexdigest(), row['pdf_sha256'])
        self.assertEqual(row['offline_capture']['content'], body['content'])
        self.call('GET', '/business/service-reports', status=403)
        self.call('GET', '/business/finance/payments', status=403)
        self.call('POST', archive + '/sign', {}, status=403)
        self.call('GET', '/reports/' + row['id'], status=403)
        with self.office.lock, self.office.db:
            old = plan_access.issue(self.office, self.office.user(self.full), workspace=True, business=True)['token']
        self.call('POST', path, body, token=old, status=403)

    def test_local_wire_rejects_ignored_bodies_queries_and_ambiguous_signed_json(self):
        body = self.capture()
        path = '/business/service-reports/offline'
        before = self.office.db.total_changes
        self.call('POST', path + '?unexpected=1', body, status=400)
        for invalid in ('{"request_id":"duplicate",' + canonical(body)[1:], '{"x":NaN}', '[1]', '\ufeff' + canonical(body)):
            self.call('POST', path, invalid.encode(), status=400)
        archive = '/business/service-reports/' + body['entry_id']
        self.call('GET', archive, {}, status=400)
        self.call('GET', archive + '/pdf', {}, status=400)
        self.call('GET', archive, headers={'Transfer-Encoding': 'chunked'}, status=400)
        self.assertEqual(self.office.db.total_changes, before)
        row = self.call('POST', path, body, status=201)[0]
        self.call('GET', '/business/service-reports/' + row['id'] + '?project_id=' + self.project, status=400)

    def test_local_conflict_diagnosis_is_read_only_strict_and_scope_limited(self):
        body = self.capture()
        path = '/business/service-reports/offline/diagnosis'
        self.assertEqual(self.call('POST', path, body)[0]['state'], 'ready')
        self.office.db.execute('UPDATE projects SET name=? WHERE id=?', ('Renamed site', self.project))
        self.office.db.commit()
        before = self.office.db.total_changes
        result = self.call('POST', path, body)[0]
        self.assertEqual(result['state'], 'context_changed')
        self.assertEqual(result['current_context']['project_name'], 'Renamed site')
        self.assertEqual(self.office.db.total_changes, before)
        self.call('POST', path+'?ignored=1', body, status=400)
        self.call('POST', path, ('{"request_id":"duplicate",'+canonical(body)[1:]).encode(), status=400)
        with self.office.lock, self.office.db:
            old = plan_access.issue(self.office, self.office.user(self.full), workspace=True, business=True,
                                    business_capabilities=['time_events'])['token']
        self.call('POST', path, body, token=old, status=403)


if __name__ == '__main__':
    unittest.main()
