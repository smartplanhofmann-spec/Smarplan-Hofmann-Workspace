"""Disposable loopback browser fixture for real customer workspace requests."""
import argparse
import base64
import hashlib
import io
import json
from pathlib import Path
import signal
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'backend/online')]

from cryptography.fernet import Fernet
from PIL import Image
from werkzeug.serving import make_server
from business_operations import BusinessOperations
from core import Office
from online.test_instance_isolation import MFA_SCHEMA
from online.web import create_app
from serve_fixture import LoopbackProxyContract

PASSWORD = 'Synthetic-browser-password-123'


class CustomerProxy(LoopbackProxyContract):
    def __call__(self, environ, start_response):
        local = environ.get('wsgi.url_scheme', 'http')+'://'+environ.get('HTTP_HOST', '')
        if environ.get('PATH_INFO', '').startswith('/api/v1/customer-workspace/') and environ.get('HTTP_ORIGIN') == local:
            environ['HTTP_ORIGIN'] = 'https://127.0.0.1'
        return super().__call__(environ, start_response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready-file', required=True, type=Path)
    args = parser.parse_args()
    def stop(_signal, _frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    with tempfile.TemporaryDirectory(prefix='customer-workspace-browser-') as directory:
        office = Office(Path(directory)/'office.sqlite3')
        server = None
        try:
            office.db.executescript(MFA_SCHEMA)
            owner = dict(id=office.add_user('owner@browser.example.test', PASSWORD, 'owner'), role='owner')
            project = office.add_project(owner, 'Kundenprojekt Berlin', 'Synthetische Kundin')
            other = office.add_project(owner, 'Privater Vorgang', 'Andere Firma')
            stream = io.BytesIO()
            Image.new('RGB', (8, 8), '#bed6c0').save(stream, format='PNG')
            original = stream.getvalue()
            api = BusinessOperations(office)
            media = api.new_media(owner, project, dict(request_id=uuid.uuid4().hex, filename='projektfoto.png',
                media_type='image/png', size=len(original), sha256=hashlib.sha256(original).hexdigest()))
            api.put_media_chunk(owner, project, media['id'], 0, original)
            api.complete_media(owner, project, media['id'], dict(request_id=uuid.uuid4().hex))
            app = create_app(office=office, key=Fernet.generate_key(), host='127.0.0.1', storage_config={})
            server = make_server('127.0.0.1', 0, CustomerProxy(app), threaded=True)
            args.ready_file.write_text(json.dumps(dict(base_url='http://127.0.0.1:'+str(server.server_port),
                owner_email='owner@browser.example.test', project_id=project, other_project_id=other,
                customer_id=office.db.execute('SELECT customer_id FROM projects WHERE id=?', (project,)).fetchone()['customer_id'],
                original_base64=base64.b64encode(original).decode(), original_sha256=hashlib.sha256(original).hexdigest(), media_id=media['id'])))
            args.ready_file.chmod(0o600)
            server.serve_forever()
        finally:
            if server:
                server.server_close()
            office.db.close()
            args.ready_file.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
