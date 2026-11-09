"""Disposable PostgreSQL HTTP fixture for actual invoice/time acceptance.

Uses the production runtime role, storage binding, MFA and document policy.
Only the guarded loopback smartplan_check database is accepted. No reset or
synthetic invoice-policy override is provided.
"""
import argparse
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'backend'))
from cryptography.fernet import Fernet
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from werkzeug.serving import make_server
from online import release
from online.store import PostgresOffice, migrate
from online.web import create_app
from online.instance import bind
from online.storage import Storage
from business_documents import Documents
from business_foundation import BusinessFoundation
from business_organization import Organization
from business_planning import Planning
from serve_fixture import LoopbackProxyContract, PASSWORD


def request(**values):
    return dict(request_id=uuid.uuid4().hex, **values)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready-file', required=True, type=Path)
    args = parser.parse_args()
    dsn = os.environ['SMARTPLAN_TEST_DSN']
    release.validate_dsns(dsn, make_conninfo(dsn, dbname='smartplan_release_check'), test_mode=True)
    with psycopg.connect(dsn, connect_timeout=5) as check:
        if check.execute("SELECT to_regclass('public.users')").fetchone()[0]:
            raise RuntimeError('The isolated browser database must be empty; existing data is never reset.')
    print('document-time fixture: migrate empty database', flush=True)
    migrate(dsn, compatibility_mode='business', require_business_modules=True)
    print('document-time fixture: bootstrap owner and separate runtime role', flush=True)
    office = PostgresOffice(dsn)
    owner_id = office.add_user('owner@browser.example.test', PASSWORD, 'owner')
    office.db.close()
    with psycopg.connect(dsn, connect_timeout=5) as connection:
        if not connection.execute("SELECT 1 FROM pg_roles WHERE rolname='smartplan-online'").fetchone():
            connection.execute('CREATE ROLE "smartplan-online" LOGIN')
        connection.execute(sql.SQL('ALTER ROLE "smartplan-online" PASSWORD {}').format(sql.Literal('synthetic-browser-runtime-only')))
    release.secure_database(dsn, test_mode=True)
    print('document-time fixture: seed through production runtime', flush=True)
    runtime = make_conninfo(dsn, user='smartplan-online', password='synthetic-browser-runtime-only')
    office = PostgresOffice(runtime)
    server = None
    def stop(_signal, _frame):
        raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    with tempfile.TemporaryDirectory(prefix='smartplan-browser-time-pg-') as temporary:
        root = Path(temporary).resolve(strict=True)
        try:
            owner = dict(id=owner_id, role='owner', email='owner@browser.example.test')
            technician_id = office.add_user('technician@browser.example.test', PASSWORD, 'technician')
            organization = Organization(office)
            current = organization.get(owner)
            organization.save(owner, request(revision=current['revision'], needs={**current['needs'], 'uses_finance': True, 'has_employees': True}, modules={name: {'visible': item['visibility_override'], 'enabled': item['enabled']} for name, item in current['modules'].items()}))
            foundation = BusinessFoundation(office)
            customer = foundation.save_contact(owner, request(name='Synthetic time buyer', entity_type='company', kinds=['customer'], addresses=[dict(purpose='billing', street='Synthetic street 1', postal_code='10115', city='Berlin', country='DE')]))
            project = office.add_project(owner, 'Synthetic time project', customer_id=customer['id'])
            other = office.add_project(owner, 'Synthetic other project', customer_id=customer['id'])
            office.assign(owner, project, technician_id)
            planning = Planning(office)
            for user_id, name in ((owner_id, 'Synthetic owner'), (technician_id, 'Synthetic technician')):
                planning.save_employee(owner, request(user_id=user_id, name=name, weekly_minutes=2400, hourly_cost_minor=3500))
            documents = Documents(office)
            documents.save_settings(owner, request(revision=0, company_name='Synthetic time seller', address_line='Synthetic seller street 1', postal_code='10115', city='Berlin', country='DE', vat_id='DE123456789', issuing_enabled=True, issuer_mode='own', einvoice_format='none', cutover_ack=True, cutover_date='2026-01-01'))
            key, instance = Fernet.generate_key(), uuid.uuid4().hex
            operator = PostgresOffice(dsn)
            try:
                operator_storage = Storage(operator, key, '127.0.0.1', config={'server': {'path': str(root / 'storage')}})
                bind(operator, instance, '127.0.0.1', key, operator_storage)
            finally:
                operator.db.close()
            storage = Storage(office, key, '127.0.0.1', config={'server': {'path': str(root / 'storage')}})
            print('document-time fixture: company storage bound, start real HTTP', flush=True)
            app = create_app(office=office, key=key, host='127.0.0.1', storage=storage, instance_id=instance)
            server = make_server('127.0.0.1', 0, LoopbackProxyContract(app), threaded=True)
            args.ready_file.write_text(json.dumps(dict(base_url='http://127.0.0.1:'+str(server.server_port), project_id=project, other_project_id=other, database='postgresql', runtime_role='smartplan-online')), encoding='utf-8')
            args.ready_file.chmod(0o600)
            server.serve_forever()
        finally:
            if server:
                server.server_close()
            office.db.close()
            args.ready_file.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
