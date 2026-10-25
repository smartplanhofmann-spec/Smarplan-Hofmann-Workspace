"""Disposable loopback-only browser fixture using the real Flask/auth/domain API.

This adapts the loopback transport to the already tested HTTPS reverse-proxy
contract. It is NOT a TLS acceptance test and is never used for deployment.
Authentication, MFA, authorization, files and persistence remain the real code.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import secrets
import sys
import tempfile
import uuid

BACKEND = Path(__file__).resolve().parents[3] / 'backend'
sys.path.insert(0, str(BACKEND))
from cryptography.fernet import Fernet
from PIL import Image
from werkzeug.serving import make_server
from core import Office
from online.web import create_app
from business_foundation import BusinessFoundation
from business_operations import BusinessOperations
from business_inventory import BusinessInventory
from business_documents import Documents
from business_planning import Planning
from inquiries import Inquiries
from business_adapters import Adapters
from business_schema import set_feature_flag

PASSWORD = 'Synthetic-browser-password-123'


def request(**data):
    return dict(request_id=uuid.uuid4().hex, **data)


def seed(office, directory):
    actors = {}
    for role in ('owner', 'technician', 'accountant'):
        email = role + '@browser.example.test'
        actors[role] = dict(id=office.add_user(email, PASSWORD, role), email=email, role=role)
    owner, technician = actors['owner'], actors['technician']
    customer = office.create_customer(owner, {'name': 'Synthetic Workshop Customer', 'email': 'customer@example.test',
        'address': 'Synthetic street 1, 00000 Testcity'})
    project = office.add_project(owner, 'Synthetic Workshop', customer_id=customer['id'])
    private = office.add_project(owner, 'Private synthetic project', 'Separate synthetic customer')
    office.assign(owner, project, technician['id'])
    office.assign(owner, project, actors['accountant']['id'])
    foundation = BusinessFoundation(office)
    status = foundation.save_status(owner, request(name='Ausführung', color='#2864da', position=0, terminal=False, active=True))
    initial=foundation.project(owner,project)
    foundation.save_project(owner, project, request(revision=initial['revision'],workspace_revision=initial['workspace_revision'],status_id=status['id'],site_address='Synthetic workshop, technical room',description='Synthetic browser acceptance project.'))
    planning = Planning(office)
    for actor in (owner, technician):
        planning.save_employee(owner, request(user_id=actor['id'], name='Synthetic ' + actor['role'], weekly_minutes=2400, hourly_cost_minor=3500))
    Inquiries(office).create(owner, request(source='manual', source_account='synthetic-browser', subject='Synthetic incoming request', message='Please call back. No confirmed order.', sender_name='Synthetic customer', sender_email='request@example.test'))
    operations = BusinessOperations(office)
    stream = io.BytesIO(); Image.new('RGB', (64, 48), '#bcd3f2').save(stream, format='PNG'); source = stream.getvalue()
    photo = directory / 'synthetic-photo.png'; photo.write_bytes(source)
    media_cases=[(technician,'site_photo','site-'+str(index)+'.png','Synthetic public site photo '+str(index)) for index in range(13)]
    media_cases.append((owner,'receipt','receipt.png','PRIVATE FINANCIAL RECEIPT'))
    for actor, purpose, filename, caption in media_cases:
        media = operations.new_media(actor, project, request(filename=filename, media_type='image/png', size=len(source), sha256=hashlib.sha256(source).hexdigest(), purpose=purpose, caption=caption))
        operations.put_media_chunk(actor, project, media['id'], 0, source)
        operations.complete_media(actor, project, media['id'], request())
    operations.save_entry(technician, project, 'defect', request(title='Synthetic cover inspection', details='Inspect the synthetic cover.', location='Technical room'))
    article = Documents(office).save_article(owner, request(code='SYN-CABLE', name='Synthetic cable', kind='material', unit='m', unit_price_net='3.00', cost_price_net='1.25', tax_rate='19', tax_category='S', currency='EUR', active=True))
    inventory = BusinessInventory(office)
    location = inventory.save_location(owner, request(name='Synthetic main store'))
    inventory.move(owner, request(kind='receive', article_id=article['id'], to_location_id=location['id'], quantity='10', unit_cost_net='1.25'))
    # Explicit synthetic-only website source. No SMTP transport is configured;
    # form acceptance may queue one approved reply, never send one.
    os.environ['SMARTPLAN_WEBSITE_LEAD_SECRET']='SPLD_'+secrets.token_urlsafe(32)
    os.environ['SMARTPLAN_CONTACT_ALLOWED_ORIGINS']='https://127.0.0.1'
    os.environ['SMARTPLAN_SMTP_FROM']='reply@browser.example.test'
    for feature in ('external.website_form','external.website_leads','external.lead_autoreply'):
        set_feature_flag(office,owner,feature,True)
    adapters=Adapters(office)
    adapter=adapters.save(owner,request(name='Synthetic public browser form',profile='website_lead_v1',enabled=True,secret_ref='SMARTPLAN_WEBSITE_LEAD_SECRET'))
    os.environ['SMARTPLAN_CONTACT_ADAPTER_ID']=adapter['id']
    adapters.approve_reply_template(owner,adapter['id'],request(revision=0,approved=True,enabled=True,subject='Ihre Anfrage',text='Guten Tag {sender_name}, die Anfrage ist eingegangen. Dies ist keine Auftragsbestätigung.'))
    office.db.commit()
    return dict(project_id=project, private_project_id=private, photo_path=str(photo))


class LoopbackProxyContract:
    def __init__(self, app): self.app = app
    def __call__(self, environ, start_response):
        if environ.get('REMOTE_ADDR') not in ('127.0.0.1', '::1'):
            start_response('403 Forbidden', [('Content-Type', 'text/plain')]); return [b'loopback fixture only']
        # A browser on HTTP loopback has a local transport Origin. Only that
        # exact local Origin is mapped to this fixture's test HTTPS origin;
        # this is not an Origin/TLS acceptance test and changes no product code.
        local_origin=environ.get('wsgi.url_scheme','http')+'://'+environ.get('HTTP_HOST','')
        if environ.get('PATH_INFO')=='/api/v1/intake/contact' and environ.get('HTTP_ORIGIN')==local_origin:
            environ['HTTP_ORIGIN']='https://127.0.0.1'
        environ['HTTP_HOST'] = '127.0.0.1'
        environ['HTTP_X_FORWARDED_PROTO'] = 'https'
        return self.app(environ, start_response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready-file', required=True, type=Path)
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    def stop(_signum, _frame): raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    with tempfile.TemporaryDirectory(prefix='smartplan-browser-synthetic-') as temp:
        directory = Path(temp)
        office = Office(directory / 'office.sqlite')
        server = None
        try:
            # Online-only schema mirrors test_workspace_api's production MFA
            # definitions. It does not replace authentication or issue sessions.
            office.db.executescript('''
                CREATE TABLE mfa(user_id TEXT PRIMARY KEY REFERENCES users(id),secret TEXT NOT NULL,
                    last_step BIGINT NOT NULL DEFAULT -1,recovery TEXT NOT NULL);
                CREATE TABLE auth_challenges(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),
                    credential TEXT NOT NULL,secret TEXT NOT NULL,expiry DOUBLE PRECISION NOT NULL,
                    failures INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE login_limits(key TEXT PRIMARY KEY,failures INTEGER NOT NULL,
                    reset_at DOUBLE PRECISION NOT NULL);
            ''')
            metadata = seed(office, directory)
            app = create_app(office=office, key=Fernet.generate_key(), host='127.0.0.1')
            server = make_server('127.0.0.1', args.port, LoopbackProxyContract(app), threaded=True)
            args.ready_file.write_text(json.dumps(dict(metadata, base_url='http://127.0.0.1:' + str(server.server_port))), encoding='utf-8')
            args.ready_file.chmod(0o600)
            server.serve_forever()
        finally:
            if server: server.server_close()
            office.db.close()
            args.ready_file.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
