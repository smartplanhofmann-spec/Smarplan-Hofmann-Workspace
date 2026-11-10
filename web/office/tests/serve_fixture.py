"""Disposable loopback-only browser fixture using the real Flask/auth/domain API.

This adapts the loopback transport to the already tested HTTPS reverse-proxy
contract. It is NOT a TLS acceptance test and is never used for deployment.
Authentication, MFA, authorization, files and persistence remain the real code.
"""
import argparse
import base64
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
import traceback
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
from business_documents import Documents, render_prepared
from business_finance import Finance
from business_planning import Planning
from business_organization import Organization
from inquiries import Inquiries
from business_adapters import Adapters
from business_schema import set_feature_flag
from project_workspace import ProjectWorkspace

PASSWORD = 'Synthetic-browser-password-123'


def request(**data):
    return dict(request_id=uuid.uuid4().hex, **data)


def seed(office, directory, *, payroll_cash=False):
    actors = {}
    for role in ('owner', 'technician', 'accountant'):
        email = role + '@browser.example.test'
        actors[role] = dict(id=office.add_user(email, PASSWORD, role), email=email, role=role)
    warehouse_email = 'warehouse@browser.example.test'
    actors['warehouse'] = dict(id=office.add_user(warehouse_email, PASSWORD, 'technician'),
                               email=warehouse_email, role='technician')
    bookkeeper_email = 'bookkeeper@browser.example.test'
    actors['bookkeeper'] = dict(id=office.add_user(bookkeeper_email, PASSWORD, 'accountant'),
                                email=bookkeeper_email, role='accountant')
    allocator_email = 'allocator@browser.example.test'
    actors['allocator'] = dict(id=office.add_user(allocator_email, PASSWORD, 'accountant'),
                               email=allocator_email, role='accountant')
    component_email = 'components@browser.example.test'
    actors['components'] = dict(id=office.add_user(component_email, PASSWORD, 'accountant'),
                                email=component_email, role='accountant')
    refund_email = 'refunds@browser.example.test'
    actors['refunds'] = dict(id=office.add_user(refund_email, PASSWORD, 'accountant'),
                             email=refund_email, role='accountant')
    capacity_email = 'capacity@browser.example.test'
    actors['capacity'] = dict(id=office.add_user(capacity_email, PASSWORD, 'accountant'),
                              email=capacity_email, role='accountant')
    refunds_v2_email = 'refunds-v2@browser.example.test'
    actors['refunds_v2'] = dict(id=office.add_user(refunds_v2_email, PASSWORD, 'accountant'),
                                email=refunds_v2_email, role='accountant')
    profile_email = 'profile-admin@browser.example.test'
    actors['profile_admin'] = dict(id=office.add_user(profile_email, PASSWORD, 'technician'),
                                   email=profile_email, role='technician')
    owner, technician = actors['owner'], actors['technician']
    organization = Organization(office)
    settings = organization.get(owner)
    organization.save(owner, request(revision=settings['revision'],
        needs={**settings['needs'], 'uses_inventory': True},
        modules={name: {'visible': item['visibility_override'], 'enabled': item['enabled']}
                 for name, item in settings['modules'].items()}))
    customer = office.create_customer(owner, {'name': 'Synthetic Workshop Customer', 'email': 'customer@example.test',
        'address': 'Synthetic street 1, 00000 Testcity'})
    project = office.add_project(owner, 'Synthetic Workshop', customer_id=customer['id'])
    second_customer = office.create_customer(owner, {'name': 'Separate synthetic customer', 'email': 'second@example.test',
        'address': 'Synthetic street 2, 00000 Testcity'})
    private = office.add_project(owner, 'Private synthetic project', customer_id=second_customer['id'])
    office.assign(owner, private, actors['components']['id'])
    allocation_target = office.add_project(owner, 'Synthetic allocation target', customer_id=second_customer['id'])
    for capacity_project in (private, allocation_target):
        office.assign(owner, capacity_project, actors['capacity']['id'])
        office.assign(owner, capacity_project, actors['refunds_v2']['id'])
    refund_customer = office.create_customer(owner, {'name': 'Separate refund fixture customer', 'email': 'refund-other@example.test',
        'address': 'Synthetic third street 3, 00000 Testcity'})
    refund_other_project = office.add_project(owner, 'Synthetic refund other customer', customer_id=refund_customer['id'])
    for refund_project in (private, allocation_target, refund_other_project):
        office.assign(owner, refund_project, actors['refunds']['id'])
    for allocation_project in (project, private, allocation_target):
        office.assign(owner, allocation_project, actors['allocator']['id'])
    office.assign(owner, project, technician['id'])
    office.assign(owner, project, actors['accountant']['id'])
    office.assign(owner, project, actors['warehouse']['id'])
    office.assign(owner, project, actors['bookkeeper']['id'])
    foundation = BusinessFoundation(office)
    # Company preparation facts require global read/admin rights, no assigned
    # cash source, accounting.prepare or finance.write. No profile is seeded.
    for permission in ('accounting.read', 'finance.read', 'accounting.admin'):
        foundation.save_grant(owner, request(user_id=actors['profile_admin']['id'], permission=permission,
                                            scope='*', effect='allow', revision=0))
    for permission in ('accounting.prepare', 'finance.write'):
        foundation.save_grant(owner, request(user_id=actors['profile_admin']['id'], permission=permission,
                                            scope='*', effect='deny', revision=0))
    foundation.save_grant(owner, request(user_id=actors['warehouse']['id'], permission='inventory.write',
                                        scope='*', effect='allow', revision=0))
    for permission in ('accounting.read', 'accounting.prepare', 'accounting.admin'):
        foundation.save_grant(owner, request(user_id=actors['bookkeeper']['id'], permission=permission,
                                            scope='*', effect='allow', revision=0))
    for permission in ('accounting.read', 'accounting.prepare', 'finance.read', 'finance.write'):
        foundation.save_grant(owner, request(user_id=actors['allocator']['id'], permission=permission,
                                            scope='*', effect='allow', revision=0))
    for permission in ('accounting.read', 'accounting.prepare'):
        foundation.save_grant(owner, request(user_id=actors['components']['id'], permission=permission,
                                            scope='*', effect='allow', revision=0))
        foundation.save_grant(owner, request(user_id=actors['refunds']['id'], permission=permission,
                                            scope='*', effect='allow', revision=0))
        foundation.save_grant(owner, request(user_id=actors['capacity']['id'], permission=permission,
                                            scope='*', effect='allow', revision=0))
        foundation.save_grant(owner, request(user_id=actors['refunds_v2']['id'], permission=permission,
                                            scope='*', effect='allow', revision=0))
    foundation.save_grant(owner, request(user_id=actors['bookkeeper']['id'], permission='documents.read',
                                        scope=project, effect='deny', revision=0))
    status = foundation.save_status(owner, request(name='Ausführung', color='#2864da', position=0, terminal=False, active=True))
    initial=foundation.project(owner,project)
    foundation.save_project(owner, project, request(revision=initial['revision'],workspace_revision=initial['workspace_revision'],status_id=status['id'],site_address='Synthetic workshop, technical room',description='Synthetic browser acceptance project.'))
    workspace = ProjectWorkspace(office)
    profile = workspace.profile(owner, project)
    workspace.save_profile(owner, project, request(revision=profile['revision'],
        start_date='2030-12-15', end_date='2031-02-20'))
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
    # Catalogue acceptance data has no stock movements. The warehouse actor
    # has inventory access only; neither prices nor finance grants are needed.
    documents = Documents(office)
    for index in range(105):
        if index == 0:
            pricing = documents.pricing_preview(owner, dict(base_cost_net='12.34', labor_hours='2',
                hourly_cost_net='20', overhead_percent='10', markup_percent='25', quantity='1',
                kind='material', unit='m', source_article_id=article['id'], source_article_revision=article['revision']))
            calculated = documents.save_article(owner, request(code=f'SYN-UNSTOCKED-{index:03d}',
                name=f'Synthetic unstocked {index:03d}', pricing=pricing['inputs'],
                pricing_hash=pricing['preview_hash'], price_confirmation=True))
        else:
            documents.save_article(owner, request(code=f'SYN-UNSTOCKED-{index:03d}',
                name=f'Synthetic unstocked {index:03d}', kind='material', unit='m',
                unit_price_net='7.00', cost_price_net='4.25', tax_rate='19', tax_category='S', currency='EUR', active=True))
    for suffix, kind, active in (('INACTIVE', 'material', False), ('SERVICE', 'service', True)):
        documents.save_article(owner, request(code='SYN-UNSTOCKED-'+suffix, name='Synthetic unstocked '+suffix,
            kind=kind, unit='m', unit_price_net='7.00', cost_price_net='4.25',
            tax_rate='19', tax_category='S', currency='EUR', active=active))
    inventory = BusinessInventory(office)
    location = inventory.save_location(owner, request(name='Synthetic main store'))
    inventory.move(owner, request(kind='receive', article_id=article['id'], to_location_id=location['id'], quantity='10', unit_cost_net='1.25'))
    documents.save_settings(owner, request(revision=0, company_name='Synthetic portal seller',
        address_line='Synthetic seller street 1', postal_code='10115', city='Berlin', country='DE',
        vat_id='DE123456789', email='seller@example.test', issuing_enabled=False, issuer_mode='own', einvoice_format='none'))
    portal_offers = []
    for offer_project, name, email, title in (
            (project, 'Synthetic Workshop Customer', 'customer@example.test', 'Synthetic portal acceptance offer'),
            (private, 'Separate synthetic customer', 'second@example.test', 'Synthetic portal decline offer')):
        draft = documents.create(owner, request(project_id=offer_project, kind='offer', title=title,
            issue_date='2026-11-02', due_date='2026-11-16',
            buyer={'name': name, 'address_line': 'Synthetic buyer street 2', 'postal_code': '10117',
                   'city': 'Berlin', 'country': 'DE', 'email': email},
            intro='Synthetic public introduction <img src=x onerror="window.__unsafe=true">', notes='Synthetic public terms',
            positions=[{'article_id': calculated['id'], 'article_revision': calculated['revision'], 'quantity': '1'}]))
        prepared = documents.prepare_finalization(owner, draft['id'], draft['revision'])
        final = documents.finalize(owner, draft['id'], render_prepared(prepared), uuid.uuid4().hex)
        original = directory / (final['id'] + '.pdf'); original.write_bytes(documents.archive(owner, final['id'], 'pdf'))
        portal_offers.append({'id': final['id'], 'title': title, 'number': final['number'], 'pdf_path': str(original)})
    # Stored synthetic legacy invoice archives for browser allocation tests.
    # Only this pre-server seed uses the existing explicit test subclass. The
    # runtime Documents class and its SQLite issuer policy are never patched;
    # real production issuance is accepted separately on PostgreSQL.
    from business_tests.test_documents import SyntheticDocuments, seed_synthetic_issuer
    synthetic = SyntheticDocuments(office)
    issuer = dict(company_name='Synthetic portal seller', address_line='Synthetic seller street 1',
        postal_code='10115', city='Berlin', country='DE', vat_id='DE123456789', email='seller@example.test',
        issuing_enabled=False, issuer_mode='own', einvoice_format='none', cutover_ack=True, cutover_date='2026-01-01')
    synthetic.save_settings(owner, request(revision=synthetic.settings(owner)['revision'], **issuer))
    seed_synthetic_issuer(synthetic, owner)
    allocation_invoices = {}
    for key, target, buyer in (('primary', project, customer['name']),
                                ('original', private, second_customer['name']),
                                ('target', allocation_target, second_customer['name']),
                                ('component_single', private, second_customer['name']),
                                ('component_multi', private, second_customer['name']),
                                ('refund_main', private, second_customer['name']),
                                ('refund_other_invoice', private, second_customer['name']),
                                ('refund_other_customer', refund_other_project, refund_customer['name']),
                                ('capacity_main', private, second_customer['name']),
                                ('capacity_legacy', private, second_customer['name']),
                                ('refunds_v2_main', private, second_customer['name']),
                                ('refunds_v2_legacy', private, second_customer['name'])):
        draft = synthetic.create(owner, request(project_id=target, kind='invoice',
            title='Synthetic stored allocation invoice ' + key, issue_date='2026-11-02', due_date='2026-11-16',
            buyer={'name': buyer, 'address_line': 'Synthetic buyer street 2', 'postal_code': '10117',
                   'city': 'Berlin', 'country': 'DE', 'email': 'buyer@example.test'},
            positions=[{'description': 'Synthetic archived service', 'quantity': '1', 'unit': 'HUR',
                        'unit_price_net': '100.00', 'tax_rate': '19', 'kind': 'labor'}] +
                      ([{'description': 'Synthetic second archive group', 'quantity': '1', 'unit': 'C62',
                         'unit_price_net': '50.00', 'tax_rate': '7', 'kind': 'material'}] if key == 'component_multi' else [])))
        prepared = synthetic.prepare_finalization(owner, draft['id'], draft['revision'])
        final = synthetic.finalize(owner, draft['id'], render_prepared(prepared), uuid.uuid4().hex)
        archive = directory / (final['id'] + '.pdf'); archive.write_bytes(documents.archive(owner, final['id'], 'pdf'))
        allocation_invoices[key] = {'id': final['id'], 'number': final['number'], 'project_id': target,
                                    'customer_id': final['customer_id'], 'buyer_name': buyer, 'pdf_path': str(archive)}
    chain_project=office.add_project(owner,'Synthetic invoice chain project',customer_id=customer['id'])
    invoice_chain=dict(project_id=chain_project)
    previous=None
    for key,kind,amount in (('advance','advance_invoice','30.00'),('cumulative','cumulative_invoice','70.00'),
                            ('final','final_invoice','100.00'),('independent','advance_invoice','30.00')):
        draft=synthetic.create(owner,request(project_id=chain_project,kind=kind,title='Synthetic chain '+key,
            issue_date='2026-11-02',due_date='2026-11-16',
            buyer=dict(name=customer['name'],address_line='Synthetic buyer street',postal_code='10117',city='Berlin',country='DE'),
            positions=[dict(description='Synthetic full contract',quantity='1',unit='C62',unit_price_net=amount,tax_rate='19',kind='service')],
            previous_document_ids=[previous] if key in ('cumulative','final') else []))
        final=synthetic.finalize(owner,draft['id'],render_prepared(synthetic.prepare_finalization(owner,draft['id'],draft['revision'])),uuid.uuid4().hex)
        invoice_chain[key]=dict(id=final['id'],number=final['number'],title=final['title'])
        previous=final['id']
    documents.save_settings(owner, request(revision=documents.settings(owner)['revision'], **issuer))
    # The payroll cash workflow isolates its financial source catalog so a
    # non-personnel bookkeeper does not inherit unrelated private payment seeds.
    accounting_payments, component_payments, refund_payments, capacity_payments, accounting_receipts = [], [], [], [], []
    allocation_shared = {"id": None}
    if not payroll_cash:
        finance = Finance(office)
        accounting_payments = []
        for kind, amount in (('receipt', '119.00'), ('refund', '5.00')):
            payment = finance.record_payment(owner, request(source_id='SYN-ACCOUNTING-' + kind,
                kind=kind, amount=amount, currency='EUR', booking_date='2026-11-01',
                reference='Synthetic accounting ' + kind, allocations=[]))
            accounting_payments.append({'id': payment['id'], 'kind': kind})
        allocation_shared = finance.record_payment(owner, request(source_id='SYN-ALLOCATION-SHARED',
            kind='receipt', amount='50.00', currency='EUR', booking_date='2026-11-01',
            reference='Synthetic allocation shared', allocations=[{'document_id': allocation_invoices['original']['id'], 'amount': '10.00'}]))
        component_payments = []
        for label, invoice_key, amount in (('single-1', 'component_single', '39.67'),
                ('single-2', 'component_single', '39.67'), ('single-3', 'component_single', '39.66'),
                ('multi', 'component_multi', '172.50')):
            payment = finance.record_payment(owner, request(source_id='SYN-COMPONENT-' + label,
                kind='receipt', amount=amount, currency='EUR', booking_date='2026-11-01',
                reference='Synthetic component ' + label,
                allocations=[{'document_id': allocation_invoices[invoice_key]['id'], 'amount': amount}]))
            component_payments.append({'id': payment['id'], 'label': label, 'amount': amount,
                                       'invoice_id': allocation_invoices[invoice_key]['id']})
        # No imported cash events or component records are seeded here. The refund
        # browser flow creates those using real authenticated forms after E1a tests.
        refund_payments = []
        for label, kind, invoice_key, amount, allocated, cash_date in (
                ('origin-a', 'receipt', 'refund_main', '49.67', '39.67', '2026-11-01'),
                ('origin-b', 'receipt', 'refund_main', '39.67', '39.67', '2026-11-02'),
                ('future', 'receipt', 'refund_main', '1.00', '1.00', '2026-11-03'),
                ('other-invoice', 'receipt', 'refund_other_invoice', '1.00', '1.00', '2026-11-01'),
                ('other-customer', 'receipt', 'refund_other_customer', '1.00', '1.00', '2026-11-01'),
                ('return-1', 'refund', 'refund_main', '26.44', '26.44', '2026-11-02'),
                ('return-2', 'refund', 'refund_main', '26.44', '26.44', '2026-11-02'),
                ('return-3', 'refund', 'refund_main', '26.46', '26.46', '2026-11-02')):
            payment = finance.record_payment(owner, request(source_id='SYN-REFUND-' + label,
                kind=kind, amount=amount, currency='EUR', booking_date='2026-11-01',
                reference='Synthetic refund ' + label,
                allocations=[{'document_id': allocation_invoices[invoice_key]['id'], 'amount': allocated}]))
            refund_payments.append({'id': payment['id'], 'label': label, 'kind': kind, 'amount': amount,
                'allocated': allocated, 'cash_date': cash_date, 'invoice_id': allocation_invoices[invoice_key]['id']})
        # Isolated financial sources only: the browser imports, documents, binds the
        # return and reuses capacity through real forms. One payment spans both writers.
        capacity_payments = []
        for label, kind, amount, main_amount, legacy_amount, cash_date in (
                ('origin-first', 'receipt', '39.67', '39.67', None, '2026-11-01'),
                ('origin-middle', 'receipt', '49.67', '39.67', None, '2026-11-01'),
                ('origin-last', 'receipt', '39.66', '39.66', None, '2026-11-01'),
                ('returned-middle', 'refund', '39.67', '39.67', None, '2026-11-02'),
                ('mixed-replacement', 'receipt', '23.22', '13.22', '10.00', '2026-11-03'),
                ('remaining-replacement', 'receipt', '26.45', '26.45', None, '2026-11-03')):
            allocations = [{'document_id': allocation_invoices['capacity_main']['id'], 'amount': main_amount}]
            if legacy_amount is not None:
                allocations.append({'document_id': allocation_invoices['capacity_legacy']['id'], 'amount': legacy_amount})
            payment = finance.record_payment(owner, request(source_id='SYN-CAPACITY-' + label,
                kind=kind, amount=amount, currency='EUR', booking_date=cash_date,
                reference='Synthetic capacity ' + label, allocations=allocations))
            capacity_payments.append({'id': payment['id'], 'label': label, 'kind': kind, 'amount': amount,
                'allocated': main_amount, 'legacy_amount': legacy_amount, 'cash_date': cash_date,
                'invoice_id': allocation_invoices['capacity_main']['id']})
        accounting_receipts = []
        for target, vendor, invoice in ((project, 'Synthetic accounting supplier', 'SYN-ACCT-001'),
                                        (private, 'Private accounting supplier', 'SYN-PRIVATE-001'),
                                        (private, 'Synthetic component supplier', 'SYN-COMP-SUPPLIER')):
            original = b'%PDF-1.4\nSynthetic accounting evidence ' + invoice.encode() + b'\n%%EOF'
            receipt = finance.capture_receipt(owner, request(project_id=target, filename=invoice + '.pdf',
                media_type='application/pdf', original_base64=base64.b64encode(original).decode(), note='Synthetic original'))
            finance.review_receipt(owner, receipt['id'], request(revision=0, vendor=vendor, invoice_number=invoice,
                issue_date='2026-11-01', net='100.00', tax='19.00', gross='119.00', currency='EUR',
                status='reviewed', note='Synthetic confirmed supplier evidence'))
            original_path = directory / (invoice + '.pdf'); original_path.write_bytes(original)
            accounting_receipts.append({'id': receipt['id'], 'vendor': vendor, 'invoice': invoice, 'original_path': str(original_path)})
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
    return dict(project_id=project, private_project_id=private, photo_path=str(photo), portal_offers=portal_offers, accounting_payments=accounting_payments,
                accounting_receipts=accounting_receipts, allocation_invoices=allocation_invoices,
                allocation_shared_payment=allocation_shared['id'], allocation_target_project=allocation_target,
                component_payments=component_payments, refund_payments=refund_payments,
                capacity_payments=capacity_payments,invoice_chain=invoice_chain)


class LoopbackProxyContract:
    def __init__(self, app): self.app = app
    def __call__(self, environ, start_response):
        if environ.get('REMOTE_ADDR') not in ('127.0.0.1', '::1'):
            start_response('403 Forbidden', [('Content-Type', 'text/plain')]); return [b'loopback fixture only']
        # A browser on HTTP loopback has a local transport Origin. Only that
        # exact local Origin is mapped to this fixture's test HTTPS origin;
        # this is not an Origin/TLS acceptance test and changes no product code.
        local_origin=environ.get('wsgi.url_scheme','http')+'://'+environ.get('HTTP_HOST','')
        if (environ.get('PATH_INFO')=='/api/v1/intake/contact' or environ.get('PATH_INFO','').startswith('/api/v1/portal/')) and environ.get('HTTP_ORIGIN')==local_origin:
            environ['HTTP_ORIGIN']='https://127.0.0.1'
        environ['HTTP_HOST'] = '127.0.0.1'
        environ['HTTP_X_FORWARDED_PROTO'] = 'https'
        return self.app(environ, start_response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ready-file', required=True, type=Path)
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--synthetic-company-events', action='store_true', help='Bind only the disposable company event fixture')
    parser.add_argument('--synthetic-speech', action='store_true', help='Inject the explicit test-only local speech transport')
    parser.add_argument('--synthetic-installation-context', action='store_true', help='Record only this disposable fixture source marker')
    parser.add_argument('--synthetic-qonto', action='store_true', help='Inject synthetic read-only Qonto replies, never a bank connection')
    parser.add_argument('--synthetic-qonto-own-key', action='store_true', help='Use the exact synthetic own-company API key header, never a bank connection')
    parser.add_argument('--synthetic-handover', action='store_true', help='Bind only the disposable company archive fixture')
    parser.add_argument('--synthetic-payroll-cash', action='store_true', help='Seed only the payroll workflow financial sources')
    args = parser.parse_args()
    def stop(_signum, _frame): raise SystemExit(0)
    signal.signal(signal.SIGTERM, stop)
    with tempfile.TemporaryDirectory(prefix='smartplan-browser-synthetic-') as temp:
        directory = Path(temp).resolve(strict=True)
        office = Office(directory / 'office.sqlite')
        server = None
        speech_patch = None
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
            metadata = seed(office, directory, payroll_cash=args.synthetic_payroll_cash)
            fixture_key = Fernet.generate_key()
            bank_feeds=None
            if args.synthetic_qonto or args.synthetic_qonto_own_key:
                from qonto_fixture import seed_qonto
                bank_feeds=seed_qonto(office,metadata,own_key=args.synthetic_qonto_own_key)
            if args.synthetic_handover or args.synthetic_company_events:
                from online.instance import bind
                from online.storage import Storage
                fixture_instance = uuid.uuid4().hex
                storage = Storage(office, fixture_key, '127.0.0.1', config={'server': {'path': str(directory/'handover-storage')}})
                bind(office, fixture_instance, '127.0.0.1', fixture_key, storage)
                metadata['handover_instance_id'] = fixture_instance
            if args.synthetic_installation_context:
                from online import installation
                marker=directory/'BUILD_SOURCE.json'
                installation.write_context(marker,'1'*40)
                installation.MARKER=marker
                metadata['installation_source_commit']='1'*40
            app = create_app(office=office, key=fixture_key, host='127.0.0.1', bank_feeds=bank_feeds,
                **({'storage':storage,'instance_id':fixture_instance} if args.synthetic_handover or args.synthetic_company_events else {}))
            original_unexpected = app.error_handler_spec[None][None][Exception]
            def synthetic_exception_diagnostic(error):
                response = original_unexpected(error)
                # Only this disposable test fixture emits stack coordinates.
                # Never include exception text, request values or frame locals.
                status = response[1] if isinstance(response, tuple) else response.status_code
                if status == 500:
                    frames = [dict(file=Path(frame.filename).name,
                                   line=frame.lineno, function=frame.name)
                              for frame in traceback.extract_tb(error.__traceback__)]
                    print('SYNTHETIC_SERVER_EXCEPTION '+json.dumps(dict(
                        type=type(error).__name__, frames=frames)), file=sys.stderr, flush=True)
                return response
            app.register_error_handler(Exception, synthetic_exception_diagnostic)
            if args.synthetic_speech:
                from unittest.mock import patch
                from business_assistant_speech import wav_bytes
                probe_path=directory/'speech-probe.json'
                probe_path.write_text('[]',encoding='utf-8')
                row=office.db.execute('SELECT instance_id FROM business_instance_identity WHERE singleton=1').fetchone()
                instance_id=row['instance_id'] if row else uuid.uuid4().hex
                if row is None:
                    with office.db:
                        office.db.execute('INSERT INTO business_instance_identity(singleton,instance_id,public_host,storage_root,vault_fingerprint,created_at) VALUES(1,?,?,?,?,?)',
                            (instance_id,'127.0.0.1',str(directory),'a'*64,datetime.now(timezone.utc).isoformat()))
                class SyntheticSpeechTransport:
                    def transcribe(self,config,audio,operation_id):
                        raw,count=wav_bytes(base64.b64encode(audio).decode())
                        attempts=json.loads(probe_path.read_text())
                        attempts.append(dict(id=operation_id,sha256=hashlib.sha256(raw).hexdigest(),audio_bytes=len(raw),samples=count))
                        probe_path.write_text(json.dumps(attempts),encoding='utf-8')
                        return 'Synthetisch erkannter Text. Bitte offene Aufgaben prüfen.'
                os.environ.update({'SMARTPLAN_ASSISTANT_SPEECH_'+key:value for key,value in dict(ENABLED='1',DATA_TRANSFER_APPROVED='1',INSTANCE_ID=instance_id,
                    ENDPOINT='https://speech.example.test/v1/audio/transcriptions',MODEL='synthetic-browser-contract',API_KEY='synthetic-never-network-test-key').items()})
                speech_patch=patch('business_assistant_speech.OpenAICompatibleSpeech',return_value=SyntheticSpeechTransport())
                speech_patch.start()
                metadata['speech_probe_path']=str(probe_path)

            server = make_server('127.0.0.1', args.port, LoopbackProxyContract(app), threaded=True)
            args.ready_file.write_text(json.dumps(dict(metadata, base_url='http://127.0.0.1:' + str(server.server_port))), encoding='utf-8')
            args.ready_file.chmod(0o600)
            server.serve_forever()
        finally:
            if server: server.server_close()
            if speech_patch: speech_patch.stop()
            office.db.close()
            args.ready_file.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
