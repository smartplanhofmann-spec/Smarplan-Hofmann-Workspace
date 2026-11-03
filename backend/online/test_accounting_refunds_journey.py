"""Independent refund-origin journeys over verified HTTPS and real TOTP MFA.

Only stored SQLite invoices use the existing explicit SyntheticDocuments test
fixture. HTTP authentication, source authorization and production issuer gates
are not patched. Genuine PostgreSQL issuance is checked separately. All cash
and company data is synthetic; no bank, tax or external provider is contacted.
"""
import http.client
import socket
import ssl
import unittest
import uuid

from business_documents import render_prepared
from business_tests.test_documents import SyntheticDocuments
from online import test_accounting_journey as cash
from online import test_accounting_allocations_journey as allocations
from online import test_accounting_components_journey as components


request = cash.request
PREFIX = '/business/accounting/refunds/events/'
ORIGIN_FIELDS = {'entry_id', 'group_id', 'origin_event_id', 'component_sequence',
    'rate', 'category', 'tax_reason', 'document_id', 'customer_id', 'project_id',
    'number', 'party_name', 'cash_date', 'evidence_reference', 'reference', 'currency',
    'amount', 'net', 'tax', 'returned_amount', 'returned_net', 'returned_tax',
    'remaining_amount', 'remaining_net', 'remaining_tax', 'lot_state_hash'}


class AccountingRefundsJourneyTests(unittest.TestCase):
    # Reuse transport/fixture methods without inheriting existing test cases.
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
    project_invoice = allocations.AccountingAllocationsJourneyTests.project_invoice
    open_item = allocations.AccountingAllocationsJourneyTests.open_item
    database = allocations.AccountingAllocationsJourneyTests.database
    allocate = components.AccountingComponentsJourneyTests.allocate

    def imported(self, payment, *, token='owner', cash_date='2026-11-02', account=None):
        source = self.source(self.company, 'payments', payment['id'], token=token)
        command = self.import_body(source, account=account)
        command['cash_date'] = cash_date
        event = self.call(self.company, '/business/accounting/events/import-payment',
                          command, token=token, status=201).json
        return source, event, command

    def component(self, event, *, token='owner'):
        path = components.PREFIX + event['id']
        state = self.call(self.company, path, token=token).json
        portion = self.call(self.company, path + '/portions', token=token).json['items'][0]
        self.assertEqual(len(portion['groups']), 1)
        body = dict(source_hash=state['source_hash'], expected_revision=state['revision'],
            state_hash=state['state_hash'], portion_id=portion['portion_id'],
            portion_state_hash=portion['portion_state_hash'],
            groups=[dict(group_id=portion['groups'][0]['group_id'], amount=portion['amount'])],
            reason='Synthetic documentary receipt component')
        preview = self.call(self.company, path + '/preview', body, token=token).json
        return self.call(self.company, path + '/confirm', request(**body,
            preview_hash=preview['preview_hash'], confirmation=True), token=token, status=201).json

    def receipt_lot(self, amount='119.00', *, invoice=None, token='owner', cash_date='2026-11-02'):
        invoice = invoice or self.invoice
        payment, _ = self.payment_record(amount=amount, allocations=[(invoice['id'], amount)], token=token)
        _, event, _ = self.imported(payment, token=token, cash_date=cash_date)
        return payment, event, self.component(event, token=token)

    def refund(self, amount='119.00', *, invoice=None, token='owner', cash_date='2026-11-02', account=None):
        invoice = invoice or self.invoice
        payment, _ = self.payment_record(amount=amount, kind='refund',
            allocations=[(invoice['id'], amount)], token=token)
        _, event, _ = self.imported(payment, token=token, cash_date=cash_date, account=account)
        return payment, event

    def state(self, event, *, token='owner'):
        return self.call(self.company, PREFIX + event['id'], token=token).json

    def portions(self, event, *, token='owner'):
        return self.call(self.company, PREFIX + event['id'] + '/portions', token=token).json['items']

    def origins(self, event, *, portion=None, token='owner'):
        portion = portion or self.portions(event, token=token)[0]
        return self.call(self.company, PREFIX + event['id'] + '/origins?portion_id=' +
                         portion['portion_id'], token=token).json['items']

    def body(self, event, *, portion=None, chosen=None, token='owner'):
        state = self.state(event, token=token)
        portion = portion or self.portions(event, token=token)[0]
        if chosen is None:
            available = self.origins(event, portion=portion, token=token)
            self.assertEqual(len(available), 1)
            chosen = [(available[0], portion['amount'])]
        return dict(source_hash=state['source_hash'], expected_revision=state['revision'],
            state_hash=state['state_hash'], portion_id=portion['portion_id'],
            portion_state_hash=portion['portion_state_hash'], origins=[dict(
                entry_id=origin['entry_id'], group_id=origin['group_id'],
                lot_state_hash=origin['lot_state_hash'], amount=amount) for origin, amount in chosen],
            reason='Synthetic explicit refund origin decision')

    def command(self, event, body, *, token='owner'):
        preview = self.call(self.company, PREFIX + event['id'] + '/preview', body, token=token).json
        return request(**body, preview_hash=preview['preview_hash'], confirmation=True)

    def confirmed(self, event, body, *, token='owner'):
        command = self.command(event, body, token=token)
        entry = self.call(self.company, PREFIX + event['id'] + '/confirm', command,
                          token=token, status=201).json
        return entry, command

    def source_rows(self):
        rows = components.AccountingComponentsJourneyTests.source_rows(self)
        for table in ('business_accounting_component_entries', 'business_accounting_component_lines',
                      'business_accounting_component_requests'):
            rows[table] = sorted(tuple(row) for row in self.office.db.execute('SELECT * FROM ' + table))
        return rows

    def test_two_distinct_lots_same_group_return_exact_cents_without_releasing_capacity(self):
        lots = [self.receipt_lot(amount) for amount in ('39.67', '39.67', '39.66')]
        self.assertEqual([(entry['net'], entry['tax']) for _, _, entry in lots],
                         [('33.34', '6.33'), ('33.33', '6.34'), ('33.33', '6.33')])
        refunds = [self.refund(amount)[1] for amount in ('26.44', '26.44', '26.46')]
        chosen_ids = {lots[0][2]['id'], lots[1][2]['id']}
        old_rows, old_op = self.source_rows(), self.open_item(self.invoice)
        old_components = {event['id']: self.call(self.company, components.PREFIX + event['id'] + '/history').json
                          for _, event, _ in lots}
        entries, commands = [], []
        for index, (event, slice_amount, expected) in enumerate(zip(refunds,
                ('13.22', '13.22', '13.23'), (('22.22', '4.22'), ('22.21', '4.23'), ('22.24', '4.22')))):
            origins = [value for value in self.origins(event) if value['entry_id'] in chosen_ids]
            self.assertEqual(len(origins), 2)
            self.assertEqual(len({origin['group_id'] for origin in origins}), 1)
            for origin in origins:
                self.assertEqual(set(origin), ORIGIN_FIELDS)
                original = next(entry for _, _, entry in lots if entry['id'] == origin['entry_id'])
                group = original['portion']['groups'][0]
                self.assertEqual((origin['component_sequence'], origin['rate'], origin['category'], origin['tax_reason']),
                                 (original['sequence'], group['rate'], group['category'], group['reason']))
            entry, command = self.confirmed(event, self.body(event,
                chosen=[(origin, slice_amount) for origin in reversed(origins)]))
            self.assertEqual((entry['net'], entry['tax']), expected)
            self.assertEqual(entry['amount'], event['amount'])
            self.assertFalse(entry['capacity_released'])
            self.assertFalse(entry['tax_result_available'])
            self.assertEqual(entry['tax_status'], 'unconfigured')
            self.assertEqual([line['entry_id'] for line in entry['lines']], sorted(chosen_ids))
            for line in entry['lines']:
                origin = next(value for value in origins if value['entry_id'] == line['entry_id'])
                self.assertEqual({key: line[key] for key in ('component_sequence', 'rate', 'category', 'tax_reason')},
                                 {key: origin[key] for key in ('component_sequence', 'rate', 'category', 'tax_reason')})
            if index == 2:
                self.assertTrue(all(line['remaining_gross'] == line['remaining_net'] ==
                                    line['remaining_tax'] == '0.00' for line in entry['lines']))
            state = self.state(event)
            self.assertEqual((state['origin_documented_amount'], state['origin_unresolved_amount']),
                             (event['amount'], '0.00'))
            self.assertEqual(self.portions(event), [])
            entries.append(entry); commands.append(command)
        self.assertEqual(self.source_rows(), old_rows)
        self.assertEqual(self.open_item(self.invoice), old_op)
        for _, event, _ in lots:
            self.assertEqual(self.call(self.company, components.PREFIX + event['id'] + '/history').json,
                             old_components[event['id']])
        for event, entry, command in zip(refunds, entries, commands):
            self.assertEqual(self.call(self.company, PREFIX + event['id'] + '/confirm', command, status=201).json, entry)
            self.assertEqual(self.call(self.company, '/business/accounting/events/' + event['id']).json, event)
            self.call(self.company, PREFIX + event['id'] + '/confirm',
                      {**command, 'request_id': uuid.uuid4().hex}, status=409)
            self.call(self.company, PREFIX + event['id'] + '/confirm',
                      {**command, 'origins': list(reversed(command['origins']))}, status=409)
        # Cash refunded really restores the Finance open amount, but R1 never restores C1 capacity.
        payment, _ = self.payment_record(amount='1.00', allocations=[(self.invoice['id'], '1.00')])
        _, event, _ = self.imported(payment)
        component_portion = self.call(self.company, components.PREFIX + event['id'] + '/portions').json['items'][0]
        self.assertFalse(component_portion['eligible'])
        self.assertEqual(component_portion['groups'][0]['remaining_gross'], '0.00')

    def test_global_lot_budget_rejects_stale_preview_and_invalid_whole_portion_without_writes(self):
        self.receipt_lot('60.00')
        # The undocumented second receipt supports actual refunds, not extra origin capacity.
        self.payment_record(amount='40.00', allocations=[(self.invoice['id'], '40.00')])
        refunds = [self.refund('40.00')[1] for unused in range(2)]
        bodies = [self.body(event) for event in refunds]
        commands = [self.command(event, body) for event, body in zip(refunds, bodies)]
        before = self.database()
        invalid = [dict(bodies[0], origins=[]), dict(bodies[0], origins=bodies[0]['origins'] * 2)]
        invalid += [dict(bodies[0], origins=[{**bodies[0]['origins'][0], 'amount': amount}])
                    for amount in ('39.99', '0.00', '-1.00', '40', 40, '40.001')]
        for body in invalid:
            self.call(self.company, PREFIX + refunds[0]['id'] + '/preview', body, status=400)
        self.assertEqual(self.database(), before)
        self.call(self.company, PREFIX + refunds[0]['id'] + '/confirm', commands[0], status=201)
        after = self.database()
        self.call(self.company, PREFIX + refunds[1]['id'] + '/confirm', commands[1], status=409)
        self.assertEqual(self.database(), after)
        remaining = self.origins(refunds[1])[0]
        self.assertEqual(remaining['remaining_amount'], '20.00')
        self.call(self.company, PREFIX + refunds[1]['id'] + '/preview', self.body(refunds[1]), status=409)

    def test_origin_source_extension_hides_history_and_pending_origins_even_for_refund_only_in_a(self):
        project_b, invoice_b = self.project_invoice()
        user, token = self.user(self.company)
        self.prepare_user(self.company, user)
        self.call(self.company, '/assignments', {'project_id': project_b, 'user_id': user})
        payment, _ = self.payment_record(amount='30.00', allocations=[(self.invoice['id'], '10.00')], token=token)
        _, receipt_event, _ = self.imported(payment, token=token)
        self.component(receipt_event, token=token)
        first = self.refund('5.00', token=token)[1]
        second = self.refund('5.00', token=token)[1]
        entry, command = self.confirmed(first, self.body(first, token=token), token=token)
        pending_body = self.body(second, token=token)
        pending_command = self.command(second, pending_body, token=token)
        self.allocate(payment, invoice_b, '20.00', token=token)
        self.permission(self.company, user, 'finance.read', effect='deny', scope=project_b)
        for suffix, body in (('', None), ('/history', None), ('/portions', None),
                ('/origins?portion_id=' + command['portion_id'], None), ('/confirm', command)):
            self.call(self.company, PREFIX + first['id'] + suffix, body, token=token, status=(403, 404))
        # A never-accepted pending command must also lose access to the selected origin.
        self.assertTrue(self.state(second, token=token)['eligible'])
        self.assertEqual(self.origins(second, token=token), [])
        for suffix, body in (('/preview', pending_body), ('/confirm', pending_command)):
            self.call(self.company, PREFIX + second['id'] + suffix, body, token=token, status=(403, 404))
        self.permission(self.company, user, 'finance.read', scope=project_b, revision=1)
        self.assertEqual(self.call(self.company, PREFIX + first['id'] + '/confirm', command,
                                  token=token, status=201).json, entry)
        self.permission(self.company, user, 'finance.write', effect='deny', scope=project_b)
        self.assertFalse(self.state(first, token=token)['writes_allowed'])
        self.call(self.company, PREFIX + first['id'] + '/history', token=token)
        self.call(self.company, PREFIX + first['id'] + '/confirm', command, token=token, status=403)
        self.permission(self.company, user, 'accounting.read', effect='deny', revision=1)
        self.call(self.company, PREFIX + first['id'], token=token, status=403)

    def test_private_original_owner_boundary_survives_later_assignment(self):
        payment, _ = self.payment_record(amount='10.00')
        _, origin_event, _ = self.imported(payment)
        self.allocate(payment, self.invoice, '10.00')
        self.component(origin_event)
        user, token = self.user(self.company)
        self.prepare_user(self.company, user)
        refund = self.refund('10.00', token=token)[1]
        selected = self.origins(refund)[0]
        body = self.body(refund, chosen=[(selected, '10.00')], token=token)
        self.assertEqual(self.origins(refund, token=token), [])
        self.call(self.company, PREFIX + refund['id'] + '/preview', body, token=token, status=(403, 404))
        entry, command = self.confirmed(refund, body)
        self.call(self.company, PREFIX + refund['id'], token=token, status=(403, 404))
        self.call(self.company, PREFIX + refund['id'] + '/history', token=token, status=(403, 404))
        self.assertEqual(self.call(self.company, PREFIX + refund['id'] + '/confirm', command, status=201).json, entry)

    def test_global_origin_aggregate_counts_hidden_refund_without_exposing_its_members(self):
        self.receipt_lot('20.00')
        project_b, invoice_b = self.project_invoice()
        self.receipt_lot('10.00', invoice=invoice_b)
        payment, _ = self.payment_record(amount='20.00', kind='refund',
            allocations=[(self.invoice['id'], '10.00'), (invoice_b['id'], '10.00')])
        _, hidden, _ = self.imported(payment)
        portion = next(value for value in self.portions(hidden) if value['document_id'] == self.invoice['id'])
        origin = self.origins(hidden, portion=portion)[0]
        hidden_body = self.body(hidden, portion=portion, chosen=[(origin, '10.00')])
        hidden_body['reason'] = 'Synthetic confidential second-project refund reason'
        hidden_entry, hidden_command = self.confirmed(hidden, hidden_body)
        user, token = self.user(self.company)
        self.prepare_user(self.company, user)
        self.permission(self.company, user, 'finance.read', effect='deny', scope=project_b)
        visible = self.refund('10.00', token=token)[1]
        self.call(self.company, PREFIX + hidden['id'], token=token, status=(403, 404))
        origins = self.origins(visible, token=token)
        self.assertEqual(len(origins), 1)
        self.assertEqual((origins[0]['returned_amount'], origins[0]['remaining_amount']), ('10.00', '10.00'))
        public = str(origins)
        for secret in (payment['id'], hidden['id'], hidden_entry['id'], hidden_command['request_id'],
                       hidden_body['reason'], self.owner['id']):
            self.assertNotIn(secret, public)
        entry, unused = self.confirmed(visible, self.body(visible, token=token), token=token)
        self.assertEqual(entry['lines'][0]['gross_before'], '10.00')
        self.assertEqual(entry['lines'][0]['remaining_gross'], '0.00')

    def test_cash_dates_accounts_and_later_cancellation_preserve_genuine_origin(self):
        payment, _ = self.payment_record(amount='20.00', allocations=[(self.invoice['id'], '20.00')])
        _, origin_event, _ = self.imported(payment, cash_date='2026-11-01')
        other_account = self.account_record(self.company, 'OTHER')
        # Refund precedes documentary component creation; only original cash dates govern.
        early = self.refund('5.00', cash_date='2026-10-31', account=other_account)[1]
        same = self.refund('5.00', cash_date='2026-11-01', account=other_account)[1]
        late = self.refund('5.00', cash_date='2026-11-02', account=other_account)[1]
        self.component(origin_event)
        valid_origin = self.origins(same)[0]
        self.assertEqual(self.origins(early), [])
        self.call(self.company, PREFIX + early['id'] + '/preview',
                  self.body(early, chosen=[(valid_origin, '5.00')]), status=409)
        self.call(self.company, '/business/accounting/accounts/' + self.account['id'], request(
            revision=self.account['revision'], name=self.account['name'], active=False, confirmation=True))
        self.confirmed(same, self.body(same))
        documents = SyntheticDocuments(self.office)
        with self.office.lock, self.office.db:
            draft = documents.cancel(self.owner, self.invoice['id'], request(
                revision=self.invoice['revision'], reason='Synthetic later invoice cancellation'))
            prepared = documents.prepare_finalization(self.owner, draft['id'], draft['revision'])
        rendered = render_prepared(prepared)
        with self.office.lock, self.office.db:
            documents.finalize(self.owner, draft['id'], rendered, uuid.uuid4().hex)
        before, op = self.source_rows(), self.open_item(self.invoice)
        entry, command = self.confirmed(late, self.body(late))
        self.assertEqual(entry['amount'], '5.00')
        self.assertEqual(self.source_rows(), before)
        self.assertEqual(self.open_item(self.invoice), op)
        self.assertEqual(self.call(self.company, PREFIX + late['id'] + '/confirm', command, status=201).json, entry)

    def test_matching_customer_does_not_allow_different_invoice_or_unresolved_refunds(self):
        self.receipt_lot('20.00')
        project_b, invoice_b = self.project_invoice()
        self.receipt_lot('20.00', invoice=invoice_b)
        refund_a = self.refund('5.00')[1]
        refund_b = self.refund('5.00', invoice=invoice_b)[1]
        wrong_origin = self.origins(refund_b)[0]
        self.call(self.company, PREFIX + refund_a['id'] + '/preview',
                  self.body(refund_a, chosen=[(wrong_origin, '5.00')]), status=409)
        project_c, invoice_c = self.project_invoice(same_customer=False)
        self.receipt_lot('10.00', invoice=invoice_c)
        mixed, _ = self.payment_record(amount='12.00', kind='refund',
            allocations=[(self.invoice['id'], '5.00'), (invoice_c['id'], '5.00')])
        _, mixed_event, _ = self.imported(mixed)
        state = self.state(mixed_event)
        self.assertEqual((state['blocked_reason'], state['origin_unresolved_amount'], state['unallocated_amount']),
                         ('source_customer_unresolved', '12.00', '2.00'))
        self.assertFalse(state['eligible'])
        for portion in self.portions(mixed_event):
            self.assertFalse(portion['eligible'])
            self.assertEqual(self.origins(mixed_event, portion=portion), [])
        unallocated, _ = self.payment_record(amount='3.00', kind='refund')
        _, event, _ = self.imported(unallocated)
        state = self.state(event)
        self.assertEqual((state['origin_documented_amount'], state['origin_unresolved_amount'],
                          state['unallocated_amount'], state['blocked_reason']), ('0.00', '3.00', '3.00', 'unallocated'))
        self.assertEqual(self.portions(event), [])
        # A real Finance refund is not silently imported by browsing R1.
        old, _ = self.payment_record(amount='1.00', kind='refund', allocations=[(self.invoice['id'], '1.00')])
        before = self.database()
        self.state(refund_a); self.origins(refund_a)
        self.assertEqual(self.database(), before)
        self.assertIsNone(self.office.db.execute('SELECT event_id FROM business_accounting_source_links '
                                                'WHERE kind=? AND source_id=?', ('payment', old['id'])).fetchone())

    def test_disabled_finance_keeps_history_readable_but_blocks_new_and_replayed_commands(self):
        self.receipt_lot('10.00')
        first = self.refund('5.00')[1]
        second = self.refund('5.00')[1]
        entry, command = self.confirmed(first, self.body(first))
        pending = self.body(second)
        pending_command = self.command(second, pending)
        settings = self.call(self.company, '/business/organization').json
        body = request(revision=settings['revision'], needs=settings['needs'], modules={
            key: dict(visible=value['visibility_override'], enabled=value['enabled'])
            for key, value in settings['modules'].items()})
        body['modules']['finance']['enabled'] = False
        changed = self.call(self.company, '/business/organization', body).json
        before = self.database()
        state = self.state(first)
        self.assertFalse(state['writes_allowed'])
        self.assertEqual(self.call(self.company, PREFIX + first['id'] + '/history').json['items'], [entry])
        self.call(self.company, PREFIX + first['id'] + '/confirm', command, status=423)
        self.call(self.company, PREFIX + second['id'] + '/preview', pending, status=423)
        self.call(self.company, PREFIX + second['id'] + '/confirm', pending_command, status=423)
        self.assertEqual(self.database(), before)
        body.update(request_id=uuid.uuid4().hex, revision=changed['revision'])
        body['modules']['finance']['enabled'] = True
        self.call(self.company, '/business/organization', body)
        self.assertEqual(self.call(self.company, PREFIX + first['id'] + '/confirm', command, status=201).json, entry)
        self.call(self.company, PREFIX + second['id'] + '/confirm', pending_command, status=201)

    def test_transport_authentication_tls_raw_guards_and_preview_are_readonly(self):
        self.receipt_lot('1.00')
        _, event = self.refund('1.00')
        body = self.body(event)
        path = PREFIX + event['id']
        before = self.database()
        self.state(event)
        self.call(self.company, path + '/portions?limit=1&offset=0')
        self.call(self.company, path + '/history?limit=1&offset=0')
        page = self.call(self.company, path + '/origins?portion_id=' + body['portion_id'] + '&limit=1&offset=0').json
        self.assertEqual(set(page), {'items', 'total', 'next_offset', 'scope'})
        self.assertEqual(page['scope'], 'authorized_sources')
        command = self.command(event, body)
        for suffix in ('?unknown=1', '/portions?limit=1&limit=2', '/history?offset=-1',
                '/origins?portion_id=' + body['portion_id'] + '&portion_id=' + body['portion_id'],
                '/origins', '/portions?limit=101', '/history?offset=100001'):
            self.call(self.company, path + suffix, status=400)
        self.call(self.company, path, {'unknown': True}, method='GET', status=400)
        self.call(self.company, path + '/preview', {**body, 'unknown': True}, status=400)
        self.call(self.company, path + '/preview', {**body, '_query': {}}, status=400)
        self.call(self.company, path + '/preview?unknown=1', body, status=400)
        self.call(self.company, path + '/confirm?limit=1&limit=2', command, status=400)
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
                response = http.client.HTTPResponse(connection); response.begin()
                self.assertEqual(response.status, 400)
                response.read()


if __name__ == '__main__':
    unittest.main()
