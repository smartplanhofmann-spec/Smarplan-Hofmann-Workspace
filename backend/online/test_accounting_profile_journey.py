"""Preparation profile through verified loopback TLS and ordinary password/TOTP.

These profile-only fixtures create no invoice archive, default profile or tax
configuration. Requests use the normal product API and synthetic office data.
"""
import http.client
import socket
import ssl
import unittest
import uuid

import business_schema
from online import test_accounting_journey as cash
from online import test_accounting_allocations_journey as tls
from online import test_accounting_profile_http as profile

PREFIX = profile.PREFIX
request = cash.request


class AccountingProfileJourneyTests(unittest.TestCase):
    setUp = cash.AccountingJourneyTests.setUp
    new_company = cash.AccountingJourneyTests.new_company
    open_app = tls.AccountingAllocationsJourneyTests.open_app
    call = tls.AccountingAllocationsJourneyTests.call
    login = cash.AccountingJourneyTests.login
    user = cash.AccountingJourneyTests.user
    permission = cash.AccountingJourneyTests.permission
    account_record = cash.AccountingJourneyTests.account_record
    payment = cash.AccountingJourneyTests.payment
    source = cash.AccountingJourneyTests.source
    import_body = cash.AccountingJourneyTests.import_body
    state = profile.AccountingProfileHTTPTests.state
    draft = profile.AccountingProfileHTTPTests.draft
    command = profile.AccountingProfileHTTPTests.command
    confirmed = profile.AccountingProfileHTTPTests.confirmed
    database = profile.AccountingProfileHTTPTests.database
    old_financial_rows = staticmethod(profile.AccountingProfileHTTPTests.old_financial_rows)

    def profile_user(self, label='profile-admin'):
        user, token = self.user(self.company, label, project=False)
        for permission in ('accounting.read', 'finance.read', 'accounting.admin'):
            self.permission(self.company, user, permission)
        return user, token

    def test_only_fresh_global_admin_plus_reads_can_confirm_without_prepare_write_or_source_grants(self):
        user, token = self.user(self.company, project=False)
        self.call(self.company, PREFIX, token=token, status=403)
        for permission in ('accounting.read', 'finance.read', 'accounting.prepare'):
            self.permission(self.company, user, permission)
        self.assertFalse(self.state(token=token)['writes_allowed'])
        body = self.draft(token=token)
        self.call(self.company, PREFIX+'/preview', body, token=token, status=403)
        for permission in ('accounting.read', 'accounting.admin'):
            self.call(self.company, '/business/settings/permissions', request(user_id=user,
                permission=permission, scope=self.company['project'], effect='allow', revision=0), status=400)
        self.permission(self.company, user, 'accounting.admin')
        self.permission(self.company, user, 'accounting.prepare', effect='deny', revision=1)
        self.permission(self.company, user, 'finance.write', effect='deny')
        self.permission(self.company, user, 'finance.read', scope=self.company['project'], effect='deny')
        self.assertTrue(self.state(token=token)['writes_allowed'])
        entry, command = self.confirmed(token=token)
        self.assertEqual(entry['created_by'], user)
        self.permission(self.company, user, 'accounting.admin', effect='deny', revision=1)
        self.assertFalse(self.state(token=token)['writes_allowed'])
        self.assertEqual(self.call(self.company, PREFIX+'/history', token=token).json['items'], [entry])
        denied = self.call(self.company, PREFIX+'/confirm', command, token=token, status=403)
        self.assertNotIn('request_resolution', denied.json)
        self.permission(self.company, user, 'accounting.admin', revision=2)
        self.permission(self.company, user, 'finance.read', effect='deny', revision=1)
        for suffix, data in (('', None), ('/history', None), ('/confirm', command)):
            self.call(self.company, PREFIX+suffix, data, token=token, status=403)
        self.permission(self.company, user, 'finance.read', revision=2)
        self.assertEqual(self.call(self.company, PREFIX+'/confirm', command, token=token, status=201).json, entry)

    def test_null_tax_answers_and_independent_dates_are_facts_only_and_leave_existing_finance_active(self):
        payment = self.payment(self.company)
        source = self.source(self.company, 'payments', payment['id'])
        original = self.import_body(source)
        event = self.call(self.company, '/business/accounting/events/import-payment', original, status=201).json
        office = self.company['office']
        rows = self.old_financial_rows(office)
        status = self.call(self.company, '/business/accounting/status').json
        entries = []
        for value in (profile.empty_profile(),
                      profile.empty_profile(vat_regime='regular', vat_effective_from='2200-12-31', bookkeeping_start='1900-01-01'),
                      profile.empty_profile(vat_regime='regular', vat_timing='cash', vat_effective_from='1900-01-01', bookkeeping_start='2200-12-31')):
            entry, command = self.confirmed(self.draft(profile=value))
            self.assertEqual(entry['profile'], value)
            entries.append((entry, command))
        self.assertEqual(self.old_financial_rows(office), rows)
        self.assertEqual(self.call(self.company, '/business/accounting/status').json, status)
        self.assertEqual(status['profile_status'], 'unconfigured')
        for entry, command in entries:
            self.assertEqual(self.call(self.company, PREFIX+'/confirm', command, status=201).json, entry)
        self.assertEqual(self.call(self.company, '/business/accounting/events/import-payment', original, status=201).json, event)
        later = self.payment(self.company, amount='1.00')
        later_source = self.source(self.company, 'payments', later['id'])
        self.call(self.company, '/business/accounting/events/import-payment', self.import_body(later_source), status=201)
        self.assertFalse(self.state()['tax_result_available'])
        self.assertEqual(self.state()['preparation_status'], 'recorded')

    def test_exact_old_receipt_outlives_later_versions_and_only_absent_stale_requests_are_terminal(self):
        first = self.command(self.draft(reason='Synthetic first simultaneous review'))
        stale = self.command(self.draft(reason='Synthetic second simultaneous review'))
        accepted = self.call(self.company, PREFIX+'/confirm', first, status=201).json
        before = self.database()
        rejected = self.call(self.company, PREFIX+'/confirm', stale, status=409)
        self.assertEqual(rejected.json.get('request_resolution'), 'not_accepted')
        mismatch = self.call(self.company, PREFIX+'/confirm', {**first, 'reason': 'Changed accepted body'}, status=409)
        self.assertNotIn('request_resolution', mismatch.json)
        self.assertEqual(self.database(), before)
        later, unused = self.confirmed(self.draft(reason='Synthetic fresh explicit second review'))
        self.assertEqual(later['revision'], 2)
        before = self.database()
        self.assertEqual(self.call(self.company, PREFIX+'/confirm', first, status=201).json, accepted)
        self.assertEqual(self.database(), before)
        self.assertEqual(self.state()['current'], later)

    def test_mode_and_finance_pause_keep_history_readable_and_accepted_commands_unresolved_until_reenabled(self):
        entry, original = self.confirmed()
        pending = self.command(self.draft(reason='Synthetic pending second version'))
        office = self.company['office']
        business_schema.set_mode(office, 'legacy')
        before = self.database()
        self.assertFalse(self.state()['writes_allowed'])
        self.assertEqual(self.call(self.company, PREFIX+'/history').json['items'], [entry])
        for command in (original, pending):
            response = self.call(self.company, PREFIX+'/confirm', command, status=409)
            self.assertNotIn('request_resolution', response.json)
        self.assertEqual(self.database(), before)
        business_schema.set_mode(office, 'business')
        settings = self.call(self.company, '/business/organization').json
        body = request(revision=settings['revision'], needs=settings['needs'], modules={
            key: dict(visible=value['visibility_override'], enabled=value['enabled'])
            for key, value in settings['modules'].items()})
        body['modules']['finance']['enabled'] = False
        changed = self.call(self.company, '/business/organization', body).json
        before = self.database()
        self.assertFalse(self.state()['writes_allowed'])
        self.assertEqual(self.call(self.company, PREFIX+'/history').json['items'], [entry])
        for command in (original, pending):
            response = self.call(self.company, PREFIX+'/confirm', command, status=423)
            self.assertNotIn('request_resolution', response.json)
        self.assertEqual(self.database(), before)
        body.update(request_id=uuid.uuid4().hex, revision=changed['revision'])
        body['modules']['finance']['enabled'] = True
        self.call(self.company, '/business/organization', body)
        self.assertEqual(self.call(self.company, PREFIX+'/confirm', original, status=201).json, entry)
        self.assertEqual(self.call(self.company, PREFIX+'/confirm', pending, status=201).json['revision'], 2)

    def test_requests_belong_to_the_authenticated_user_and_profile_to_one_office(self):
        user, token = self.profile_user()
        first, command = self.confirmed()
        body = self.draft(reason='Synthetic second actor explicit statement', token=token)
        second_command = self.command(body, token=token)
        second_command['request_id'] = command['request_id']
        second = self.call(self.company, PREFIX+'/confirm', second_command, token=token, status=201).json
        self.assertEqual(second['created_by'], user)
        self.assertNotEqual(second['id'], first['id'])
        self.assertEqual(second['revision'], 2)
        other = self.new_company('beta-profile')
        self.assertEqual(self.state(company=other)['preparation_status'], 'unrecorded')
        self.call(other, PREFIX, token=self.company['token'], status=401)
        self.call(self.company, PREFIX, token=other['token'], status=401)
        self.assertEqual(self.call(self.company, PREFIX+'/confirm', command, status=201).json, first)
        self.assertEqual(self.call(self.company, PREFIX+'/confirm', second_command, token=token, status=201).json, second)

    def test_real_tls_hostname_host_and_profile_wire_framing_fail_closed_without_saving(self):
        body = self.draft(); command = self.command(body); before = self.database()
        for suffix in ('', '/history'):
            self.call(self.company, PREFIX+suffix, {}, method='GET', status=400)
        self.call(self.company, PREFIX+'/preview?unknown=1', body, status=400)
        self.call(self.company, PREFIX+'/confirm?revision=0', command, status=400)
        self.call(self.company, PREFIX+'/history?limit=1&limit=2', status=400)
        self.call(self.company, PREFIX, token=None, status=401)
        for context, hostname in ((ssl.create_default_context(), self.company['host']),
                                  (self.company['tls'], 'other.example.test')):
            with self.assertRaises(ssl.SSLCertVerificationError):
                with socket.create_connection(('127.0.0.1', self.company['server'].server_port), timeout=5) as raw:
                    with context.wrap_socket(raw, server_hostname=hostname):
                        self.fail('Untrusted CA or wrong certificate hostname was accepted')
        for host, payload in (('other.example.test', b'{}'),
                              (self.company['host'], b'{"expected_revision":0,"expected_revision":0}')):
            with socket.create_connection(('127.0.0.1', self.company['server'].server_port), timeout=5) as raw:
                with self.company['tls'].wrap_socket(raw, server_hostname=self.company['host']) as connection:
                    headers = ('POST /api/v1'+PREFIX+'/preview HTTP/1.1\r\nHost: '+host+
                        '\r\nConnection: close\r\nContent-Type: application/json\r\nContent-Length: '+str(len(payload))+
                        '\r\nAuthorization: Bearer '+self.company['token']+'\r\n\r\n')
                    connection.sendall(headers.encode('ascii')+payload)
                    response = http.client.HTTPResponse(connection); response.begin()
                    self.assertEqual(response.status, 400); response.read()
        self.assertEqual(self.database(), before)
        self.assertEqual(self.state()['revision'], 0)


if __name__ == '__main__':
    unittest.main()
