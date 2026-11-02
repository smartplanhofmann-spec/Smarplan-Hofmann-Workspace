"""Independent E1b-2 journeys over verified loopback HTTPS and real TOTP MFA.

Only saved SQLite invoice fixtures use the explicitly test-only
SyntheticDocuments class. No application authentication, issuing policy or
authorization is patched. Genuine PostgreSQL issuance is verified separately.
All payments/originals are synthetic; no bank, email or tax service is called.
"""
from copy import deepcopy
import http.client
import socket
import ssl
import unittest
import uuid

from business_documents import render_prepared
from business_tests.test_documents import SyntheticDocuments
from online import test_accounting_journey as cash
from online import test_accounting_allocations_journey as allocations


request = cash.request
PREFIX = '/business/accounting/components/events/'
GROUP_FIELDS = {'group_id', 'rate', 'category', 'reason', 'net', 'tax', 'gross',
    'documented_net', 'documented_tax', 'documented_gross',
    'remaining_net', 'remaining_tax', 'remaining_gross'}


class AccountingComponentsJourneyTests(unittest.TestCase):
    # Fixture helper reuse, deliberately without inheriting old test cases.
    base_setup = cash.AccountingJourneyTests.setUp
    setUp = allocations.AccountingAllocationsJourneyTests.setUp
    new_company = cash.AccountingJourneyTests.new_company
    open_app = allocations.AccountingAllocationsJourneyTests.open_app
    call = allocations.AccountingAllocationsJourneyTests.call
    login = cash.AccountingJourneyTests.login
    user = cash.AccountingJourneyTests.user
    permission = cash.AccountingJourneyTests.permission
    account_record = cash.AccountingJourneyTests.account_record
    source = cash.AccountingJourneyTests.source
    import_body = cash.AccountingJourneyTests.import_body
    prepare_user = cash.AccountingJourneyTests.prepare_user
    incoming = cash.AccountingJourneyTests.incoming
    payout_body = cash.AccountingJourneyTests.payout_body
    payment_record = allocations.AccountingAllocationsJourneyTests.payment_record
    imported = allocations.AccountingAllocationsJourneyTests.imported
    project_invoice = allocations.AccountingAllocationsJourneyTests.project_invoice
    open_item = allocations.AccountingAllocationsJourneyTests.open_item
    database = allocations.AccountingAllocationsJourneyTests.database

    def invoice_with_groups(self):
        """Real rendering/archive, explicit synthetic SQLite-only issuer."""
        documents = SyntheticDocuments(self.office)
        with self.office.lock, self.office.db:
            draft = documents.create(self.owner, request(project_id=self.company['project'],
                kind='invoice', title='Synthetic multiple archived groups', issue_date='2026-11-02',
                due_date='2026-11-02', buyer={'name': 'Synthetic group customer',
                    'address_line': 'Synthetic buyer street 2', 'postal_code': '10117',
                    'city': 'Berlin', 'country': 'DE'}, positions=[
                    {'description': label, 'quantity': '1', 'unit': 'C62', 'unit_price_net': net,
                     'tax_rate': rate, 'kind': 'material'} for label, net, rate in (
                        ('Synthetic standard group', '100.00', '19'),
                        ('Synthetic second group', '50.00', '7'),
                        ('Synthetic zero group', '0.00', '5'))]))
            prepared = documents.prepare_finalization(self.owner, draft['id'], draft['revision'])
        rendered = render_prepared(prepared)
        with self.office.lock, self.office.db:
            return documents.finalize(self.owner, draft['id'], rendered, uuid.uuid4().hex)

    def allocate(self, payment, invoice, amount, *, token='owner'):
        path = allocations.PREFIX + payment['id']
        state = self.call(self.company, path, token=token).json
        candidates = self.call(self.company, path + '/candidates', token=token).json['items']
        target = next(row for row in candidates if row['document_id'] == invoice['id'])
        body = dict(source_hash=state['source_hash'], expected_revision=state['revision'],
            state_hash=state['state_hash'], customer_id=target['customer_id'], document_id=invoice['id'],
            document_state_hash=target['document_state_hash'], amount=amount,
            reason='Synthetic prior additional allocation')
        preview = self.call(self.company, path + '/preview', body, token=token).json
        return self.call(self.company, path + '/assign', request(**body,
            preview_hash=preview['preview_hash'], confirmation=True), token=token, status=201).json

    def state(self, event, *, token='owner'):
        return self.call(self.company, PREFIX + event['id'], token=token).json

    def portions(self, event, *, token='owner'):
        return self.call(self.company, PREFIX + event['id'] + '/portions', token=token).json['items']

    def component_body(self, event, *, portion=None, groups=None, token='owner'):
        state = self.state(event, token=token)
        portion = portion or self.portions(event, token=token)[0]
        if groups is None:
            self.assertEqual(len(portion['groups']), 1)
            groups = [{'group_id': portion['groups'][0]['group_id'], 'amount': portion['amount']}]
        return dict(source_hash=state['source_hash'], expected_revision=state['revision'],
            state_hash=state['state_hash'], portion_id=portion['portion_id'],
            portion_state_hash=portion['portion_state_hash'], groups=groups,
            reason='Synthetic explicitly confirmed documentary components')

    def confirmed(self, event, body, *, token='owner'):
        path = PREFIX + event['id']
        preview = self.call(self.company, path + '/preview', body, token=token).json
        command = request(**body, preview_hash=preview['preview_hash'], confirmation=True)
        entry = self.call(self.company, path + '/confirm', command, token=token, status=201).json
        return entry, command

    def source_rows(self):
        tables = ('business_documents', 'business_document_archives', 'business_document_versions',
            'business_document_numbers', 'business_document_counters', 'business_payments',
            'business_payment_allocations', 'business_finance_requests', 'business_accounting_cash_events',
            'business_accounting_source_links', 'business_accounting_requests',
            'business_accounting_allocation_entries', 'business_accounting_allocation_requests',
            'business_incoming_receipts', 'business_receipt_reviews')
        return {table: sorted(tuple(row) for row in self.office.db.execute('SELECT * FROM ' + table))
                for table in tables}

    def test_three_whole_original_and_additional_portions_preserve_cents_sources_and_paid_op(self):
        events = []
        for index, amount in enumerate(('39.67', '39.67', '39.66')):
            payment, _ = self.payment_record(amount=amount,
                allocations=[] if index == 1 else [(self.invoice['id'], amount)])
            _, event, _ = self.imported(payment)
            if index == 1:
                self.allocate(payment, self.invoice, amount)
            events.append(event)
        self.call(self.company, '/business/accounting/accounts/' + self.account['id'], request(
            revision=self.account['revision'], name=self.account['name'], active=False, confirmation=True))
        before = self.source_rows()
        op = self.open_item(self.invoice)
        self.assertEqual(op['open'], '0.00')
        kinds, entries, commands, group_ids = [], [], [], []
        for event, expected in zip(events, (('33.34', '6.33'), ('33.33', '6.34'), ('33.33', '6.33'))):
            portion = self.portions(event)[0]
            kinds.append(portion['kind'])
            group_ids.append(portion['groups'][0]['group_id'])
            entry, command = self.confirmed(event, self.component_body(event, portion=portion))
            entries.append(entry)
            commands.append(command)
            self.assertEqual((entry['net'], entry['tax']), expected)
            self.assertEqual(entry['amount'], event['amount'])
            self.assertFalse(entry['tax_result_available'])
            self.assertEqual(entry['tax_status'], 'unconfigured')
            state = self.state(event)
            self.assertEqual((state['documented_amount'], state['undocumented_amount']), (event['amount'], '0.00'))
            self.assertEqual(self.portions(event), [])
        self.assertEqual(kinds, ['original_allocation', 'additional_allocation', 'original_allocation'])
        self.assertEqual(len(set(group_ids)), 1)
        self.assertEqual(entries[-1]['lines'][0]['gross_after'], '119.00')
        self.assertEqual(entries[-1]['lines'][0]['remaining_gross'], '0.00')
        self.assertEqual(self.source_rows(), before)
        self.assertEqual(self.open_item(self.invoice), op)
        for event, entry, command in zip(events, entries, commands):
            self.assertEqual(self.call(self.company, PREFIX + event['id'] + '/confirm', command, status=201).json, entry)
            self.assertEqual(self.call(self.company, '/business/accounting/events/' + event['id']).json, event)

    def test_multigroup_explicit_cents_zero_group_and_invalid_inputs_never_rewrite_sources(self):
        invoice = self.invoice_with_groups()
        payment, _ = self.payment_record(amount='100.00', allocations=[(invoice['id'], '86.25')])
        _, event, _ = self.imported(payment)
        portion = self.portions(event)[0]
        self.assertEqual({row['rate'] for row in portion['groups']}, {'19', '7'})
        self.assertEqual(len(invoice['totals']['tax_breakdown']), 3)
        for group in portion['groups']:
            self.assertEqual(set(group), GROUP_FIELDS)
        groups = [{'group_id': group['group_id'], 'amount': '60.00' if group['rate'] == '19' else '26.25'}
                  for group in portion['groups']]
        body = self.component_body(event, portion=portion, groups=groups)
        before = self.database()
        invalid_groups = [[], [groups[0], groups[0]]]
        invalid_groups += [[{**groups[0], 'amount': value}, groups[1]]
                          for value in ('-1.00', '0.00', '60.001', '60,00', 60.0, True)]
        for invalid in invalid_groups:
            self.call(self.company, PREFIX + event['id'] + '/preview',
                      {**body, 'groups': invalid}, status=400)
        self.call(self.company, PREFIX + event['id'] + '/preview',
            {**body, 'groups': [{'group_id': 'f' * 64, 'amount': '86.25'}]}, status=409)
        missing_cent = deepcopy(body)
        missing_cent['groups'][0]['amount'] = '59.99' if groups[0]['amount'] == '60.00' else '26.24'
        self.call(self.company, PREFIX + event['id'] + '/preview', missing_cent, status=400)
        self.assertEqual(self.database(), before)
        preview = self.call(self.company, PREFIX + event['id'] + '/preview', body).json
        self.assertEqual(self.database(), before)
        self.assertEqual((preview['net'], preview['tax'], preview['amount']), ('74.95', '11.30', '86.25'))
        originals, op = self.source_rows(), self.open_item(invoice)
        entry, _ = self.confirmed(event, body)
        self.assertEqual([row['group_id'] for row in entry['lines']], sorted(row['group_id'] for row in groups))
        state = self.state(event)
        self.assertEqual((state['documented_amount'], state['undocumented_amount'], state['unallocated_amount']),
                         ('86.25', '13.75', '13.75'))
        self.assertEqual(self.source_rows(), originals)
        self.assertEqual(self.open_item(invoice), op)

    def test_private_other_payment_contributes_to_global_group_without_disclosing_its_identifiers(self):
        private, _ = self.payment_record(amount='60.00')
        _, private_event, _ = self.imported(private)
        self.allocate(private, self.invoice, '60.00')
        self.confirmed(private_event, self.component_body(private_event))
        user, token = self.user(self.company)
        self.prepare_user(self.company, user)
        own, _ = self.payment_record(amount='59.00', allocations=[(self.invoice['id'], '59.00')], token=token)
        _, event, _ = self.imported(own, token=token)
        self.call(self.company, PREFIX + private_event['id'], token=token, status=(403, 404))
        portion = self.portions(event, token=token)[0]
        group = portion['groups'][0]
        self.assertEqual(set(group), GROUP_FIELDS)
        self.assertEqual((group['documented_gross'], group['remaining_gross']), ('60.00', '59.00'))
        response = self.call(self.company, PREFIX + event['id'] + '/portions', token=token)
        for identifier in (private['id'], private_event['id'], self.owner['id']):
            self.assertNotIn(identifier.encode(), response.data)
        entry, _ = self.confirmed(event, self.component_body(event, portion=portion, token=token), token=token)
        self.assertEqual((entry['net'], entry['tax']), ('49.58', '9.42'))
        self.assertEqual(entry['created_by'], user)

    def test_competing_event_group_changes_invalidate_preview_without_partial_writes(self):
        events = []
        for _ in range(2):
            payment, _ = self.payment_record(amount='59.50', allocations=[(self.invoice['id'], '59.50')])
            events.append(self.imported(payment)[1])
        bodies = [self.component_body(event) for event in events]
        stale = self.call(self.company, PREFIX + events[1]['id'] + '/preview', bodies[1]).json
        first, command = self.confirmed(events[0], bodies[0])
        before = self.database()
        self.call(self.company, PREFIX + events[1]['id'] + '/confirm', request(**bodies[1],
            preview_hash=stale['preview_hash'], confirmation=True), status=409)
        self.call(self.company, PREFIX + events[0]['id'] + '/confirm',
                  {**command, 'reason': 'Changed reason under the same request'}, status=409)
        self.call(self.company, PREFIX + events[0]['id'] + '/confirm',
                  {**command, 'request_id': uuid.uuid4().hex}, status=409)
        self.assertEqual(self.database(), before)
        fresh_body = self.component_body(events[1])
        self.assertNotEqual(fresh_body['portion_state_hash'], bodies[1]['portion_state_hash'])
        self.assertEqual(fresh_body['source_hash'], bodies[1]['source_hash'])
        second, _ = self.confirmed(events[1], fresh_body)
        self.assertEqual((first['net'], first['tax'], second['net'], second['tax']), ('50.00', '9.50', '50.00', '9.50'))

    def test_small_payment_on_larger_archived_group_keeps_distinct_input_and_source_limits(self):
        invoice = allocations.seed_legacy_invoice(self.office, self.owner,
            self.company['project'], net='1000000000.00')
        payment, _ = self.payment_record(amount='1.00', allocations=[(invoice['id'], '1.00')])
        _, event, _ = self.imported(payment)
        portion = self.portions(event)[0]
        self.assertEqual((portion['amount'], portion['groups'][0]['gross']), ('1.00', '1190000000.00'))
        entry, _ = self.confirmed(event, self.component_body(event, portion=portion))
        self.assertEqual((entry['net'], entry['tax']), ('0.84', '0.16'))
        self.assertEqual(entry['lines'][0]['remaining_gross'], '1189999999.00')

    def test_review_change_blocks_new_payout_components_but_historical_replay_keeps_original_review(self):
        receipt, original = self.incoming(self.company)
        events = []
        for _ in range(2):
            source = self.source(self.company, 'receipts', receipt['id'])
            events.append(self.call(self.company, '/business/accounting/events/payout',
                self.payout_body(source, amount='39.67'), status=201).json)
        portion = self.portions(events[0])[0]
        self.assertEqual(portion['kind'], 'supplier_payout')
        self.assertEqual(portion['review_revision'], 1)
        group = portion['groups'][0]
        self.assertEqual((group['rate'], group['category'], group['reason']), (None, None, None))
        first, command = self.confirmed(events[0], self.component_body(events[0], portion=portion))
        pending_body = self.component_body(events[1])
        self.call(self.company, '/business/finance/receipts/' + receipt['id'], request(revision=1,
            vendor=receipt['vendor'], invoice_number=receipt['invoice_number'], issue_date=receipt['issue_date'],
            net='100.00', tax='19.00', gross='119.00', currency='EUR', status='reviewed',
            note='New review with unchanged totals still requires explicit clarification'))
        self.assertFalse(self.state(events[1])['eligible'])
        self.call(self.company, PREFIX + events[1]['id'] + '/preview', pending_body, status=409)
        self.assertEqual(self.call(self.company, PREFIX + events[0]['id'] + '/confirm', command, status=201).json, first)
        self.assertEqual(first['portion']['review_revision'], 1)
        self.assertEqual(self.call(self.company, '/business/accounting/events/' + events[0]['id']).json, events[0])
        self.assertEqual(self.call(self.company, '/business/finance/receipts/' + receipt['id'] + '/original').data, original)

    def test_source_and_target_read_revocation_hides_all_parts_and_precedes_historical_replay(self):
        project_b, invoice_b = self.project_invoice()
        user, token = self.user(self.company)
        self.prepare_user(self.company, user)
        self.call(self.company, '/assignments', {'project_id': project_b, 'user_id': user})
        payment, _ = self.payment_record(amount='30.00', allocations=[(self.invoice['id'], '10.00')], token=token)
        _, event, _ = self.imported(payment, token=token)
        parts = self.portions(event, token=token)
        first_part = next(part for part in parts if part['kind'] == 'original_allocation')
        entry, command = self.confirmed(event, self.component_body(event, portion=first_part, token=token), token=token)
        self.allocate(payment, invoice_b, '20.00', token=token)
        self.assertEqual(self.call(self.company, PREFIX + event['id'] + '/confirm', command,
                                  token=token, status=201).json, entry)
        pending = self.component_body(event, token=token)
        self.permission(self.company, user, 'finance.read', effect='deny', scope=project_b)
        for suffix, body in (('', None), ('/portions', None), ('/history', None), ('/preview', pending), ('/confirm', command)):
            self.call(self.company, PREFIX + event['id'] + suffix, body, token=token, status=(403, 404))
        self.call(self.company, '/business/documents/' + invoice_b['id'], token=token, status=(403, 404))
        self.permission(self.company, user, 'finance.read', scope=project_b, revision=1)
        self.assertEqual(self.call(self.company, PREFIX + event['id'] + '/confirm', command, token=token, status=201).json, entry)
        self.permission(self.company, user, 'finance.write', effect='deny', scope=project_b)
        self.assertFalse(self.state(event, token=token)['writes_allowed'])
        self.call(self.company, PREFIX + event['id'] + '/history', token=token)
        self.call(self.company, PREFIX + event['id'] + '/confirm', command, token=token, status=403)
        self.permission(self.company, user, 'accounting.read', effect='deny', revision=1)
        self.call(self.company, PREFIX + event['id'], token=token, status=403)

    def test_refund_does_not_release_capacity_and_new_legitimate_receipt_stays_readable(self):
        payment, _ = self.payment_record(allocations=[(self.invoice['id'], '119.00')])
        _, original, _ = self.imported(payment)
        first, command = self.confirmed(original, self.component_body(original))
        refund, _ = self.payment_record(kind='refund', allocations=[(self.invoice['id'], '119.00')])
        _, refund_event, _ = self.imported(refund)
        refund_state = self.state(refund_event)
        self.assertEqual((refund_state['source_kind'], refund_state['blocked_reason']),
                         ('customer_refund', 'refund_origin_unresolved'))
        self.assertFalse(refund_state['eligible'])
        second, _ = self.payment_record(allocations=[(self.invoice['id'], '119.00')])
        _, second_event, _ = self.imported(second)
        state = self.state(second_event)
        self.assertEqual(state['undocumented_amount'], '119.00')
        portion = self.portions(second_event)[0]
        self.assertFalse(portion['eligible'])
        self.assertEqual(portion['groups'][0]['remaining_gross'], '0.00')
        self.call(self.company, PREFIX + second_event['id'] + '/preview',
                  self.component_body(second_event, portion=portion), status=409)
        self.assertEqual(self.call(self.company, PREFIX + original['id'] + '/confirm', command, status=201).json, first)
        self.assertEqual(self.open_item(self.invoice)['open'], '0.00')

    def test_transport_authentication_certificates_and_readonly_preview_reject_ambiguity(self):
        payment, _ = self.payment_record(amount='1.00', allocations=[(self.invoice['id'], '1.00')])
        _, event, _ = self.imported(payment)
        body = self.component_body(event)
        path = PREFIX + event['id']
        before = self.database()
        self.state(event)
        self.call(self.company, path + '/portions?limit=1&offset=0')
        self.call(self.company, path + '/history?limit=1&offset=0')
        preview = self.call(self.company, path + '/preview', body).json
        self.assertEqual(self.database(), before)
        for suffix in ('?unknown=1', '/portions?limit=1&limit=2', '/history?offset=-1',
                       '/portions?limit=101', '/history?offset=100001'):
            self.call(self.company, path + suffix, status=400)
        self.call(self.company, path, {'unknown': True}, method='GET', status=400)
        self.call(self.company, path + '/preview', {**body, 'unknown': True}, status=400)
        self.call(self.company, path + '/preview?unknown=1', body, status=400)
        self.call(self.company, path + '/confirm?limit=1&limit=2', request(**body,
            preview_hash=preview['preview_hash'], confirmation=True), status=400)
        self.assertEqual(self.database(), before)
        self.call(self.company, path, token=None, status=401)
        for context, hostname in ((ssl.create_default_context(), self.company['host']),
                                  (self.company['tls'], 'other.example.test')):
            with self.assertRaises(ssl.SSLCertVerificationError):
                with socket.create_connection(('127.0.0.1', self.company['server'].server_port), timeout=5) as raw:
                    with context.wrap_socket(raw, server_hostname=hostname):
                        self.fail('Untrusted CA or wrong certificate hostname was accepted')
        with socket.create_connection(('127.0.0.1', self.company['server'].server_port), timeout=5) as raw:
            with self.company['tls'].wrap_socket(raw, server_hostname=self.company['host']) as connection:
                connection.sendall(('GET /api/v1' + path + ' HTTP/1.1\r\nHost: other.example.test\r\n'
                    'Connection: close\r\nAuthorization: Bearer ' + self.company['token'] + '\r\n\r\n').encode('ascii'))
                response = http.client.HTTPResponse(connection)
                response.begin()
                self.assertEqual(response.status, 400)
                response.read()


if __name__ == '__main__':
    unittest.main()
