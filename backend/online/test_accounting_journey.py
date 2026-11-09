"""Independent accounting journeys through real Flask routes, MFA and SQLite.

All companies, users and payment evidence are synthetic. These cases exercise
the normal authorization, immutable sources and restore paths. They do not
bypass the PostgreSQL-only invoice issuing policy: allocated final invoices
are covered by the separate PostgreSQL suite. No banking service is contacted.
"""
import base64
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
import uuid

from cryptography.fernet import Fernet

from backend.backup import backup
from core import Office
from backend.restore import restore
from online.auth import totp
from online.instance import bind
from online.storage import Storage
from online.test_instance_isolation import MFA_SCHEMA
from online.web import create_app


def request(**values):
    return {'request_id': uuid.uuid4().hex, **values}


class AccountingJourneyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-accounting-journey-')
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.company = self.new_company('alpha')
        self.account = self.account_record(self.company)

    def new_company(self, label):
        office = Office(self.directory / (label + '.sqlite3'))
        self.addCleanup(office.db.close)
        office.db.executescript(MFA_SCHEMA)
        office.add_user('owner@example.test', 'Synthetic-accounting-owner-password-123', 'owner')
        company = dict(office=office, label=label, host=label + '.example.test',
            key=Fernet.generate_key(), instance_id=uuid.uuid4().hex,
            root=self.directory / (label + '-files'), mfa={})
        storage = Storage(office, company['key'], company['host'],
                          config={'server': {'path': str(company['root'])}})
        bind(office, company['instance_id'], company['host'], company['key'], storage)
        self.open_app(company, storage=storage)
        company['token'] = self.login(company, 'owner@example.test', 'Synthetic-accounting-owner-password-123')
        company['project'] = self.call(company, '/projects', {
            'name': 'Synthetic ' + label + ' accounting project',
            'customer': 'Synthetic ' + label + ' customer'}, status=201).json['id']
        return company

    def open_app(self, company, *, storage=None):
        storage = storage or Storage(company['office'], company['key'], company['host'],
            config={'server': {'path': str(company['root'])}})
        company['client'] = create_app(office=company['office'], key=company['key'],
            host=company['host'], instance_id=company['instance_id'], storage=storage).test_client()

    def call(self, company, path, body=None, *, token='owner', status=200, method=None,
             offline_origin=None):
        token = company.get('token') if token == 'owner' else token
        method = method or ('POST' if body is not None else 'GET')
        headers = {'Authorization': 'Bearer ' + token} if token else {}
        if offline_origin is not None:
            headers['X-Smartplan-Offline-Binding'] = offline_origin
        reply = company['client'].open('/api/v1' + path, method=method,
            base_url='https://' + company['host'], json=body,
            headers=headers)
        # Diagnostics do not print authentication responses or original files.
        if isinstance(status, tuple):
            self.assertIn(reply.status_code, status, (method, path, reply.status_code))
        else:
            self.assertEqual(reply.status_code, status, (method, path, reply.status_code))
        return reply

    def login(self, company, email, password, *, advance=False):
        pending = self.call(company, '/login', {'email': email, 'password': password}, token=None).json
        self.assertNotIn('token', pending)
        if pending.get('enrollment'):
            company['mfa'][email] = pending['enrollment']['secret']
        code = totp(company['mfa'][email], int(time.time() // 30) + int(advance))
        return self.call(company, '/login/verify', {'challenge': pending['challenge'], 'code': code}, token=None).json['token']

    def user(self, company, label='bookkeeper', *, project=True):
        email, password = label + '@example.test', 'Synthetic-accounting-user-password-123'
        identifier = self.call(company, '/users', {
            'email': email, 'password': password, 'role': 'accountant'}, status=201).json['id']
        if project:
            self.call(company, '/assignments', {'project_id': company['project'], 'user_id': identifier})
        return identifier, self.login(company, email, password)

    def permission(self, company, user, permission, *, effect='allow', scope='*', revision=0):
        return self.call(company, '/business/settings/permissions', request(
            user_id=user, permission=permission, scope=scope,
            effect=effect, revision=revision)).json

    def payment(self, company, *, kind='receipt', amount='119.00', token='owner'):
        return self.call(company, '/business/finance/payments', request(
            source_id='synthetic-manual-payment-' + uuid.uuid4().hex,
            kind=kind, amount=amount, currency='EUR', booking_date='2026-11-02',
            reference='Synthetic confirmed ' + kind, allocations=[]), token=token).json

    def incoming(self, company, *, project=True, token='owner', original=None):
        original = original or (b'%PDF-1.4\nSynthetic independent accounting original ' +
                               uuid.uuid4().hex.encode() + b'\n%%EOF')
        value = dict(filename='synthetic-accounting-receipt.pdf', media_type='application/pdf',
            original_base64=base64.b64encode(original).decode(), note='Synthetic evidence only')
        if project:
            value['project_id'] = company['project']
        receipt = self.call(company, '/business/finance/receipts', request(**value), token=token).json
        reviewed = self.call(company, '/business/finance/receipts/' + receipt['id'], request(
            revision=0, vendor='Synthetic supplier', invoice_number='SYN-' + receipt['id'][:8],
            issue_date='2026-11-01', net='100.00', tax='19.00', gross='119.00',
            currency='EUR', status='reviewed', note='Synthetic reviewed amount')).json
        self.assertEqual(reviewed['sha256'], hashlib.sha256(original).hexdigest())
        return reviewed, original

    def account_record(self, company, code='MAIN'):
        return self.call(company, '/business/accounting/accounts', request(
            code=code, name='Synthetic ' + code + ' account', kind='bank',
            confirmation=True), status=201).json

    def source(self, company, kind, identifier, *, token='owner'):
        value = self.call(company, '/business/accounting/sources/' + kind + '?limit=100', token=token).json
        field = 'payment_id' if kind == 'payments' else 'receipt_id'
        return next(row for row in value['items'] if row[field] == identifier)

    def payout_body(self, source, *, account=None, amount='59.50', evidence=None):
        account = account or self.account
        return request(**{key: source[key] for key in (
            'receipt_id', 'source_hash', 'review_revision', 'review_sha256', 'original_sha256')},
            account_id=account['id'], account_revision=account['revision'],
            expected_cash_revision=source['cash_revision'], amount=amount,
            cash_date='2026-11-02', evidence_reference=evidence or 'EVIDENCE-' + uuid.uuid4().hex,
            reference='Synthetic manually confirmed supplier payment', confirmation=True)

    def import_body(self, source, *, account=None, evidence=None):
        account = account or self.account
        return request(payment_id=source['payment_id'], source_hash=source['source_hash'],
            account_id=account['id'], account_revision=account['revision'], cash_date='2026-11-02',
            evidence_reference=evidence or 'EVIDENCE-' + uuid.uuid4().hex, confirmation=True)

    def prepare_user(self, company, user):
        for permission in ('accounting.read', 'accounting.prepare'):
            self.permission(company, user, permission)

    def legacy_sources(self, company):
        """Exact prior rows, including original bytes, without changing their guards."""
        return {table: sorted(tuple(row) for row in company['office'].db.execute('SELECT * FROM ' + table))
            for table in ('business_payments', 'business_payment_allocations',
                          'business_incoming_receipts', 'business_receipt_reviews')}

    def test_partial_payouts_replay_and_restart_preserve_original_sources_and_account_version(self):
        company = self.company
        receipt, original = self.incoming(company)
        source = self.source(company, 'receipts', receipt['id'])
        before = self.legacy_sources(company)
        first_body = self.payout_body(source)
        first = self.call(company, '/business/accounting/events/payout', first_body, status=201).json
        self.assertEqual((first['direction'], first['amount'], first['classification_status']),
                         ('out', '59.50', 'unclassified'))
        self.assertIn('tax_profile_unconfigured', first['unresolved_reasons'])
        self.assertEqual(first['source']['snapshot']['review_revision'], 1)
        self.assertEqual(first['source']['snapshot']['original_sha256'], hashlib.sha256(original).hexdigest())
        self.assertEqual(self.call(company, '/business/accounting/events/payout', first_body, status=201).json, first)
        self.call(company, '/business/accounting/events/payout', dict(first_body, amount='1.00'), status=409)
        source = self.source(company, 'receipts', receipt['id'])
        self.assertEqual((source['cash_revision'], source['paid_amount'], source['remaining_amount']),
                         (1, '59.50', '59.50'))
        self.call(company, '/business/accounting/events/payout', self.payout_body(source, amount='59.51'), status=409)
        second = self.call(company, '/business/accounting/events/payout', self.payout_body(source), status=201).json
        self.assertEqual(second['sequence'], first['sequence'] + 1)
        final = self.source(company, 'receipts', receipt['id'])
        self.assertEqual((final['cash_revision'], final['paid_amount'], final['remaining_amount'],
                          final['payable'], final['blocked_reason']), (2, '119.00', '0.00', False, 'paid'))
        self.call(company, '/business/accounting/accounts/' + self.account['id'], request(
            revision=1, name='Synthetic renamed inactive account', active=False, confirmation=True))
        self.assertEqual(self.call(company, '/business/accounting/events/payout', first_body, status=201).json, first)
        self.assertEqual(first['account']['revision'], 1)
        self.assertEqual(self.legacy_sources(company), before)
        company['office'].db.close()
        company['office'] = Office(self.directory / 'alpha.sqlite3')
        self.addCleanup(company['office'].db.close)
        self.open_app(company)
        self.assertEqual(self.call(company, '/business/accounting/events/' + first['id']).json, first)
        self.assertEqual(self.call(company, '/business/accounting/events/payout', first_body, status=201).json, first)
        self.assertEqual(self.call(company, '/business/finance/receipts/' + receipt['id'] + '/original').data, original)
        self.assertEqual(self.legacy_sources(company), before)

    def test_existing_payments_and_refunds_are_imported_once_without_creating_payments(self):
        company = self.company
        payment = self.payment(company)
        refund = self.payment(company, kind='refund', amount='5.00')
        before = self.legacy_sources(company)
        source = self.source(company, 'payments', payment['id'])
        body = self.import_body(source)
        event = self.call(company, '/business/accounting/events/import-payment', body, status=201).json
        self.assertEqual((event['direction'], event['amount']), ('in', '119.00'))
        self.assertEqual(event['source']['snapshot']['kind'], 'receipt')
        self.assertEqual(event['source']['snapshot']['unallocated'], '119.00')
        self.assertEqual(self.call(company, '/business/accounting/events/import-payment', body, status=201).json, event)
        self.assertEqual(self.source(company, 'payments', payment['id'])['linked_event_id'], event['id'])
        another = self.account_record(company, 'OTHER')
        self.call(company, '/business/accounting/events/import-payment', self.import_body(source, account=another), status=409)
        refund_source = self.source(company, 'payments', refund['id'])
        refund_event = self.call(company, '/business/accounting/events/import-payment',
            self.import_body(refund_source), status=201).json
        self.assertEqual((refund_event['direction'], refund_event['amount'], refund_event['source']['snapshot']['kind']),
                         ('out', '5.00', 'refund'))
        self.assertIn('refund_origin_unresolved', refund_event['unresolved_reasons'])
        # Evidence uniqueness spans the two routes; the attempted payout stays absent.
        receipt, _ = self.incoming(company)
        after_capture = self.legacy_sources(company)
        self.call(company, '/business/accounting/events/payout', self.payout_body(
            self.source(company, 'receipts', receipt['id']), evidence=body['evidence_reference']), status=409)
        self.assertEqual(self.legacy_sources(company), after_capture)
        for table in ('business_payments', 'business_payment_allocations'):
            self.assertEqual(self.legacy_sources(company)[table], before[table])
        listing = self.call(company, '/business/accounting/events').json
        self.assertEqual((listing['total'], listing['scope'], listing['tax_result_available']),
                         (2, 'authorized_sources', False))

    def test_fresh_global_and_source_permissions_gate_reads_and_historical_replays(self):
        company = self.company
        user, token = self.user(company)
        receipt, _ = self.incoming(company)
        self.call(company, '/business/accounting/status', token=token, status=403)
        self.call(company, '/business/settings/permissions', request(
            user_id=user, permission='accounting.read', scope=company['project'],
            effect='allow', revision=0), status=400)
        self.call(company, '/business/accounting/status', token=token, status=403)
        self.permission(company, user, 'accounting.read')
        source = self.source(company, 'receipts', receipt['id'], token=token)
        body = self.payout_body(source)
        self.call(company, '/business/accounting/events/payout', body, token=token, status=403)
        self.permission(company, user, 'accounting.prepare')
        event = self.call(company, '/business/accounting/events/payout', body, token=token, status=201).json
        self.permission(company, user, 'finance.read', scope=company['project'], effect='deny')
        self.assertEqual(self.call(company, '/business/accounting/events', token=token).json['items'], [])
        self.assertEqual(self.call(company, '/business/accounting/sources/receipts', token=token).json['total'], 0)
        self.call(company, '/business/accounting/events/' + event['id'], token=token, status=403)
        self.call(company, '/business/accounting/events/payout', body, token=token, status=403)
        self.permission(company, user, 'finance.read', scope=company['project'], revision=1)
        self.assertEqual(self.call(company, '/business/accounting/events/payout', body, token=token, status=201).json, event)
        self.permission(company, user, 'accounting.prepare', effect='deny', revision=1)
        self.call(company, '/business/accounting/events/payout', body, token=token, status=403)
        self.assertEqual(self.call(company, '/business/accounting/events/' + event['id'], token=token).json, event)
        self.permission(company, user, 'finance.read', effect='deny')
        self.call(company, '/business/accounting/events', token=token, status=403)

    def test_private_sources_stay_private_and_duplicate_original_never_opens_another_budget(self):
        company = self.company
        hidden_payment = self.payment(company)
        hidden_receipt, original = self.incoming(company, project=False)
        hidden_body = self.payout_body(self.source(company, 'receipts', hidden_receipt['id']), amount='50.00')
        hidden_event = self.call(company, '/business/accounting/events/payout', hidden_body, status=201).json
        user, token = self.user(company)
        self.prepare_user(company, user)
        self.assertEqual(self.call(company, '/business/accounting/sources/payments', token=token).json['items'], [])
        self.assertEqual(self.call(company, '/business/accounting/sources/receipts', token=token).json['items'], [])
        self.call(company, '/business/accounting/events/' + hidden_event['id'], token=token, status=(403, 404))
        hidden_source = self.source(company, 'payments', hidden_payment['id'])
        self.call(company, '/business/accounting/events/import-payment', self.import_body(hidden_source), token=token, status=(403, 404))
        own_payment = self.payment(company, token=token, amount='13.00')
        visible = self.call(company, '/business/accounting/sources/payments', token=token).json
        self.assertEqual([row['payment_id'] for row in visible['items']], [own_payment['id']])
        clone, _ = self.incoming(company, project=False, token=token, original=original)
        source = self.source(company, 'receipts', clone['id'], token=token)
        self.assertEqual((source['payable'], source['blocked_reason'], source['paid_amount'], source['cash_revision']),
                         (False, 'duplicate_original', '0.00', 0))
        serialized = json.dumps(source)
        self.assertNotIn(hidden_receipt['id'], serialized)
        self.assertNotIn(hidden_event['id'], serialized)
        self.call(company, '/business/accounting/events/payout', self.payout_body(source), token=token, status=409)
        self.assertEqual(self.call(company, '/business/accounting/events', token=token).json['total'], 0)

    def test_changed_receipt_review_blocks_new_payout_but_preserves_historical_replay(self):
        company = self.company
        receipt, original = self.incoming(company)
        source = self.source(company, 'receipts', receipt['id'])
        body = self.payout_body(source, amount='50.00')
        event = self.call(company, '/business/accounting/events/payout', body, status=201).json
        self.call(company, '/business/finance/receipts/' + receipt['id'], request(
            revision=1, vendor='Synthetic supplier', invoice_number='SYN-revised', issue_date='2026-11-01',
            net='20.00', tax='3.80', gross='23.80', currency='EUR', status='reviewed', note='Synthetic review correction'))
        current = self.source(company, 'receipts', receipt['id'])
        self.assertEqual((current['review_revision'], current['paid_amount'], current['remaining_amount'],
                          current['payable'], current['blocked_reason']), (2, '50.00', '0.00', False, 'review_changed'))
        self.assertEqual(self.call(company, '/business/accounting/events/payout', body, status=201).json, event)
        self.call(company, '/business/accounting/events/payout', self.payout_body(current, amount='1.00'), status=409)
        self.call(company, '/business/accounting/events/payout', dict(body, request_id=uuid.uuid4().hex), status=409)
        historical = self.call(company, '/business/accounting/events/' + event['id']).json
        self.assertEqual(historical, event)
        self.assertEqual(historical['source']['snapshot']['gross'], '119.00')
        self.assertEqual(self.call(company, '/business/finance/receipts/' + receipt['id'] + '/original').data, original)

    def test_status_strict_inputs_and_visible_pagination_do_not_claim_tax_results(self):
        company = self.company
        self.call(company, '/business/accounting/status', token=None, status=401)
        status = self.call(company, '/business/accounting/status').json
        self.assertEqual((status['profile_status'], status['tax_status'], status['tax_result_available'],
                          status['scope'], status['writes_allowed']), ('unconfigured', 'unconfigured', False, 'authorized_sources', True))
        self.call(company, '/business/accounting/accounts', request(code='main', name='Duplicate', kind='cash', confirmation=True), status=409)
        receipt, _ = self.incoming(company)
        source = self.source(company, 'receipts', receipt['id'])
        for amount in ('1.001', '01.00', '-1.00', '0.00', '1000000000.00', 1.0):
            self.call(company, '/business/accounting/events/payout', self.payout_body(source, amount=amount), status=400)
        for suffix in ('?limit=0', '?offset=-1', '?limit=1&limit=2', '?project_id=' + company['project']):
            self.call(company, '/business/accounting/events' + suffix, status=400)
        self.call(company, '/business/accounting/status?unknown=true', status=400)
        body = self.payout_body(source)
        self.call(company, '/business/accounting/events/payout', dict(body, tax_status='ist'), status=400)
        self.call(company, '/business/accounting/events/payout', dict(body, cash_date='2026-02-30'), status=400)
        for amount in ('1.00', '2.00', '3.00'):
            payment = self.payment(company, amount=amount)
            self.call(company, '/business/accounting/events/import-payment',
                self.import_body(self.source(company, 'payments', payment['id'])), status=201)
        before = company['office'].db.total_changes
        first = self.call(company, '/business/accounting/events?limit=2').json
        second = self.call(company, '/business/accounting/events?limit=2&offset=2').json
        self.assertEqual(company['office'].db.total_changes, before)
        self.assertEqual((first['total'], first['next_offset'], second['next_offset']), (3, 2, None))
        self.assertEqual([row['amount'] for row in first['items'] + second['items']], ['3.00', '2.00', '1.00'])
        self.assertNotIn('hidden_count', first)
        self.assertNotIn('profit', first)

    def test_separate_company_database_and_tokens_cannot_read_or_import_foreign_sources(self):
        alpha, beta = self.company, self.new_company('beta')
        beta_account = self.account_record(beta)
        receipt, _ = self.incoming(alpha)
        source = self.source(alpha, 'receipts', receipt['id'])
        body = self.payout_body(source)
        event = self.call(alpha, '/business/accounting/events/payout', body, status=201).json
        self.call(beta, '/business/accounting/events', token=alpha['token'], status=401)
        self.call(beta, '/business/accounting/events/' + event['id'], status=404)
        self.call(beta, '/business/accounting/events/payout',
                  self.payout_body(source, account=beta_account), status=404)
        self.assertEqual(self.call(beta, '/business/accounting/events').json['total'], 0)
        local_receipt, _ = self.incoming(beta)
        local = self.call(beta, '/business/accounting/events/payout', self.payout_body(
            self.source(beta, 'receipts', local_receipt['id']), account=beta_account,
            evidence=body['evidence_reference']), status=201).json
        self.assertEqual(local['sequence'], 1)
        self.assertNotEqual(local['id'], event['id'])
        self.assertEqual(self.call(alpha, '/business/accounting/events').json['total'], 1)

    def test_actual_sqlite_restore_preserves_events_and_blocks_new_writes_until_operator_reconciliation(self):
        company = self.company
        receipt, original = self.incoming(company)
        body = self.payout_body(self.source(company, 'receipts', receipt['id']))
        event = self.call(company, '/business/accounting/events/payout', body, status=201).json
        saved = backup(self.directory / 'alpha.sqlite3', self.directory / 'before-restore.sqlite3')
        restored = restore(saved, self.directory / 'restored-alpha.sqlite3')
        office = Office(restored)
        self.addCleanup(office.db.close)
        clone = {**company, 'office': office}
        self.open_app(clone)
        self.call(clone, '/business/accounting/events', token=company['token'], status=401)
        clone['token'] = self.login(clone, 'owner@example.test', 'Synthetic-accounting-owner-password-123', advance=True)
        self.assertEqual(self.call(clone, '/business/accounting/events/' + event['id']).json, event)
        self.assertFalse(self.call(clone, '/business/accounting/status').json['writes_allowed'])
        self.call(clone, '/business/accounting/events/payout', body, status=409)
        self.call(clone, '/business/accounting/events/payout', self.payout_body(
            self.source(clone, 'receipts', receipt['id'])), status=409)
        self.assertEqual(self.call(clone, '/business/accounting/events').json['total'], 1)
        self.assertEqual(self.call(clone, '/business/finance/receipts/' + receipt['id'] + '/original').data, original)
        state = dict(office.db.execute('SELECT * FROM business_restore_state WHERE singleton=1').fetchone())
        self.assertEqual(state['financial_reconciliation_required'], 1)
        self.assertEqual(len(state['restore_id']), 32)


if __name__ == '__main__':
    unittest.main()
