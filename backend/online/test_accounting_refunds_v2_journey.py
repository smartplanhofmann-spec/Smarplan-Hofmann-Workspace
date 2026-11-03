"""Independent R2/C2 cycles through real verified loopback HTTPS and TOTP.

Only saved legacy SQLite invoice archives use the explicit synthetic issuer.
All payments, imports, origin decisions and component writes use authenticated
product routes. No bank, provider or non-test database is contacted.
"""
import http.client
import socket
import ssl
import unittest
import uuid

from online import test_accounting_capacity_journey as capacity
from online import test_accounting_refunds_journey as refunds


PREFIX = '/business/accounting/refunds/v2/events/'
request = refunds.request
STATE_FIELDS = {'event_id', 'source_hash', 'revision', 'state_hash', 'source_kind',
    'amount', 'currency', 'cash_date', 'evidence_reference', 'reference',
    'origin_documented_amount', 'origin_unresolved_amount', 'unallocated_amount',
    'eligible', 'blocked_reason', 'writes_allowed', 'capacity_released', 'scope',
    'tax_status', 'tax_result_available'}
PORTION_FIELDS = {'portion_id', 'kind', 'event_id', 'document_id', 'customer_id',
    'project_id', 'number', 'party_name', 'amount', 'currency', 'payload_sha256',
    'pdf_sha256', 'capacity_ownership_id', 'ownership_id', 'writer', 'action',
    'portion_state_hash', 'eligible', 'blocked_reason'}


class AccountingRefundsV2JourneyTests(unittest.TestCase):
    base_setup = capacity.AccountingCapacityJourneyTests.base_setup
    setUp = capacity.AccountingCapacityJourneyTests.setUp
    new_company = capacity.AccountingCapacityJourneyTests.new_company
    open_app = capacity.AccountingCapacityJourneyTests.open_app
    call = capacity.AccountingCapacityJourneyTests.call
    login = capacity.AccountingCapacityJourneyTests.login
    user = capacity.AccountingCapacityJourneyTests.user
    permission = capacity.AccountingCapacityJourneyTests.permission
    account_record = capacity.AccountingCapacityJourneyTests.account_record
    source = capacity.AccountingCapacityJourneyTests.source
    import_body = capacity.AccountingCapacityJourneyTests.import_body
    prepare_user = capacity.AccountingCapacityJourneyTests.prepare_user
    payment_record = capacity.AccountingCapacityJourneyTests.payment_record
    project_invoice = capacity.AccountingCapacityJourneyTests.project_invoice
    open_item = capacity.AccountingCapacityJourneyTests.open_item
    database = capacity.AccountingCapacityJourneyTests.database
    allocate = capacity.AccountingCapacityJourneyTests.allocate
    imported = capacity.AccountingCapacityJourneyTests.imported
    component = capacity.AccountingCapacityJourneyTests.component
    receipt_lot = capacity.AccountingCapacityJourneyTests.receipt_lot
    refund = capacity.AccountingCapacityJourneyTests.refund
    state = capacity.AccountingCapacityJourneyTests.state
    portions = capacity.AccountingCapacityJourneyTests.portions
    origins = capacity.AccountingCapacityJourneyTests.origins
    body = capacity.AccountingCapacityJourneyTests.body
    command = capacity.AccountingCapacityJourneyTests.command
    confirmed = capacity.AccountingCapacityJourneyTests.confirmed
    bind = capacity.AccountingCapacityJourneyTests.bind
    source_rows = capacity.AccountingCapacityJourneyTests.source_rows
    cstate = capacity.AccountingCapacityJourneyTests.cstate

    def replacement(self, amount, *, invoice=None, token='owner', cash_date='2026-11-02'):
        invoice = invoice or self.invoice
        payment, unused = self.payment_record(amount=amount, allocations=[(invoice['id'], amount)], token=token)
        unused_source, event, unused_command = self.imported(payment, token=token, cash_date=cash_date)
        return payment, event

    def cbody(self, event, *, document_id=None, token='owner'):
        state = self.cstate(event, token=token)
        portions = self.call(self.company, capacity.PREFIX + event['id'] + '/portions', token=token).json['items']
        portion = next(value for value in portions if document_id is None or value['document_id'] == document_id)
        self.assertEqual(len(portion['groups']), 1)
        return dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            portion_id=portion['portion_id'], portion_state_hash=portion['portion_state_hash'], action=portion['action'],
            groups=[dict(group_id=portion['groups'][0]['group_id'], amount=portion['amount'])],
            reason='Synthetic exact reuse during versioned refund cycle')

    def cconfirmed(self, event, *, document_id=None, token='owner'):
        path = capacity.PREFIX + event['id']
        body = self.cbody(event, document_id=document_id, token=token)
        preview = self.call(self.company, path + '/preview', body, token=token).json
        command = request(**body, preview_hash=preview['preview_hash'], confirmation=True)
        entry = self.call(self.company, path + '/confirm', command, token=token, status=201).json
        return entry, command

    def reused(self, *, invoice=None, amount='20.00', token='owner', origin_date='2026-11-02'):
        invoice = invoice or self.invoice
        unused, original_event, original = self.receipt_lot(invoice=invoice, token=token)
        unused, refund = self.refund('20.00', invoice=invoice, token=token)
        returned, r1_command = self.bind(refund, original, '20.00', token=token)
        unused, event = self.replacement(amount, invoice=invoice, token=token, cash_date=origin_date)
        entry, command = self.cconfirmed(event, token=token)
        return dict(original_event=original_event, original=original, refund_event=refund,
            returned=returned, r1_command=r1_command, event=event, entry=entry, command=command)

    def rstate(self, event, *, token='owner'):
        value = self.call(self.company, PREFIX + event['id'], token=token).json
        self.assertEqual(set(value), STATE_FIELDS)
        self.assertFalse(value['capacity_released'])
        self.assertFalse(value['tax_result_available'])
        return value

    def rportion(self, event, *, document_id=None, token='owner'):
        page = self.call(self.company, PREFIX + event['id'] + '/portions', token=token).json
        self.assertEqual(set(page), {'items', 'total', 'next_offset', 'scope'})
        portion = next(value for value in page['items'] if document_id is None or value['document_id'] == document_id)
        self.assertEqual(set(portion), PORTION_FIELDS)
        return portion

    def rorigins(self, event, *, portion=None, token='owner'):
        portion = portion or self.rportion(event, token=token)
        page = self.call(self.company, PREFIX + event['id'] + '/origins?portion_id=' + portion['portion_id'], token=token).json
        self.assertEqual(set(page), {'items', 'total', 'next_offset', 'scope'})
        for value in page['items']:
            self.assertEqual(set(value), refunds.ORIGIN_FIELDS | {'origin_version'})
        return page['items']

    def rbody(self, event, *, chosen=None, document_id=None, token='owner'):
        state = self.rstate(event, token=token)
        portion = self.rportion(event, document_id=document_id, token=token)
        if chosen is None:
            available = self.rorigins(event, portion=portion, token=token)
            chosen = [(next(value for value in available if value['origin_version'] == 'c2'), portion['amount'])]
        return dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
            portion_id=portion['portion_id'], portion_state_hash=portion['portion_state_hash'], action=portion['action'],
            origins=[dict(origin_version=origin['origin_version'], entry_id=origin['entry_id'], group_id=origin['group_id'],
                          lot_state_hash=origin['lot_state_hash'], amount=amount) for origin, amount in chosen],
            reason='Synthetic explicit versioned positive origins for whole refund')

    def rcommand(self, event, body=None, *, token='owner'):
        body = self.rbody(event, token=token) if body is None else body
        preview = self.call(self.company, PREFIX + event['id'] + '/preview', body, token=token).json
        return request(**body, preview_hash=preview['preview_hash'], confirmation=True)

    def rconfirmed(self, event, body=None, *, token='owner'):
        command = self.rcommand(event, body, token=token)
        entry = self.call(self.company, PREFIX + event['id'] + '/confirm', command, token=token, status=201).json
        return entry, command

    def test_mixed_original_and_reused_lots_keep_r1_cents_and_support_two_new_complete_cycles(self):
        lots = [self.receipt_lot(amount) for amount in ('39.67', '39.67', '39.66')]
        middle = lots[1][2]
        self.assertEqual((middle['net'], middle['tax']), ('33.33', '6.34'))
        unused, original_refund = self.refund('13.22')
        r1_entry, r1_command = self.bind(original_refund, middle, '13.22')
        unused, first_positive = self.replacement('13.22')
        first_c2, first_c2_command = self.cconfirmed(first_positive)
        self.assertEqual((first_c2['net'], first_c2['tax']), ('11.11', '2.11'))
        unused, mixed = self.refund('26.44')
        origins = self.rorigins(mixed)
        original = next(value for value in origins if value['origin_version'] == 'c1' and value['entry_id'] == middle['id'])
        reused = next(value for value in origins if value['origin_version'] == 'c2' and value['entry_id'] == first_c2['id'])
        self.assertEqual((original['returned_amount'], original['returned_net'], original['returned_tax']), ('13.22', '11.11', '2.11'))
        before, old_op = self.source_rows(), self.open_item(self.invoice)
        mixed_entry, mixed_command = self.rconfirmed(mixed, self.rbody(mixed, chosen=[(reused, '13.22'), (original, '13.22')]))
        self.assertEqual((mixed_entry['net'], mixed_entry['tax']), ('22.21', '4.23'))
        self.assertEqual([value['origin_version'] for value in mixed_entry['lines']], ['c1', 'c2'])
        self.assertEqual((mixed_entry['lines'][0]['gross_before'], mixed_entry['lines'][0]['tax_before']), ('13.22', '2.11'))
        self.assertEqual(self.source_rows(), before)
        self.assertEqual(self.open_item(self.invoice), old_op)
        unused, next_positive = self.replacement('26.44')
        current, unused_command = self.cconfirmed(next_positive)
        self.assertEqual((current['net'], current['tax']), ('22.21', '4.23'))
        for unused in range(2):
            unused_payment, next_refund = self.refund('26.44')
            origin = next(value for value in self.rorigins(next_refund)
                          if value['origin_version'] == 'c2' and value['entry_id'] == current['id'])
            returned, unused_command = self.rconfirmed(next_refund, self.rbody(next_refund, chosen=[(origin, '26.44')]))
            self.assertEqual((returned['net'], returned['tax']), ('22.21', '4.23'))
            unused_payment, next_positive = self.replacement('26.44')
            current, unused_command = self.cconfirmed(next_positive)
            self.assertEqual((current['net'], current['tax']), ('22.21', '4.23'))
        unused, final_refund = self.refund('13.23')
        original = next(value for value in self.rorigins(final_refund)
                        if value['origin_version'] == 'c1' and value['entry_id'] == middle['id'])
        last, unused_command = self.rconfirmed(final_refund, self.rbody(final_refund, chosen=[(original, '13.23')]))
        line = last['lines'][0]
        self.assertEqual((line['gross_after'], line['net_after'], line['tax_after']), ('39.67', '33.33', '6.34'))
        self.assertEqual((line['remaining_gross'], line['remaining_net'], line['remaining_tax']), ('0.00', '0.00', '0.00'))
        for path, command, expected in ((refunds.PREFIX + original_refund['id'], r1_command, r1_entry),
                (capacity.PREFIX + first_positive['id'], first_c2_command, first_c2),
                (PREFIX + mixed['id'], mixed_command, mixed_entry)):
            self.assertEqual(self.call(self.company, path + '/confirm', command, status=201).json, expected)
        self.assertFalse(mixed_entry['capacity_released'])

    def test_r2_can_clarify_the_unimported_finance_refund_that_blocks_new_positive_capacity(self):
        source = self.reused()
        payment, unused = self.payment_record(amount='10.00', kind='refund', allocations=[(self.invoice['id'], '10.00')])
        unused, replacement = self.replacement('10.00')
        portion = self.call(self.company, capacity.PREFIX + replacement['id'] + '/portions').json['items'][0]
        self.assertFalse(portion['eligible'])
        self.assertEqual(portion['pending_blocked_reason'], 'refund_origin_unresolved')
        unused, event, unused = self.imported(payment)
        self.assertEqual(self.rportion(event)['action'], 'takeover_and_bind')
        origin = next(value for value in self.rorigins(event) if value['origin_version'] == 'c2' and value['entry_id'] == source['entry']['id'])
        entry, unused = self.rconfirmed(event, self.rbody(event, chosen=[(origin, '10.00')]))
        self.assertFalse(entry['capacity_released'])
        body = self.cbody(replacement)
        self.assertEqual(body['action'], 'document_current')
        positive, unused = self.cconfirmed(replacement)
        self.assertEqual((positive['net'], positive['tax']), (entry['net'], entry['tax']))

    def test_carried_c2_origin_scope_extension_hides_r2_history_and_replay(self):
        project_b, invoice_b = self.project_invoice()
        user, token = self.user(self.company)
        self.prepare_user(self.company, user)
        self.call(self.company, '/assignments', {'project_id': project_b, 'user_id': user})
        payment, unused = self.payment_record(amount='149.00', allocations=[(self.invoice['id'], '119.00')], token=token)
        unused, original_event, unused = self.imported(payment, token=token)
        original = self.component(original_event, token=token)
        unused, r1 = self.refund('20.00', token=token)
        self.bind(r1, original, '20.00', token=token)
        unused, positive = self.replacement('20.00', token=token)
        origin, unused_command = self.cconfirmed(positive, token=token)
        unused, event = self.refund('10.00', token=token)
        entry, command = self.rconfirmed(event, token=token)
        self.assertEqual(entry['lines'][0]['entry_id'], origin['id'])
        self.allocate(payment, invoice_b, '30.00', token=token)
        self.permission(self.company, user, 'finance.read', effect='deny', scope=project_b)
        for suffix, body in (('', None), ('/history', None), ('/portions', None), ('/confirm', command)):
            self.call(self.company, PREFIX + event['id'] + suffix, body, token=token, status=(403, 404))
        self.permission(self.company, user, 'finance.read', scope=project_b, revision=1)
        self.assertEqual(self.call(self.company, PREFIX + event['id'] + '/confirm', command, token=token, status=201).json, entry)
        self.permission(self.company, user, 'finance.write', effect='deny', scope=project_b)
        self.assertFalse(self.rstate(event, token=token)['writes_allowed'])
        self.call(self.company, PREFIX + event['id'] + '/history', token=token)
        response = self.call(self.company, PREFIX + event['id'] + '/confirm', command, token=token, status=403)
        self.assertNotIn('request_resolution', response.json)

    def test_valid_multi_invoice_event_authorization_cycle_is_finite_and_keeps_full_scope(self):
        project_b, invoice_b = self.project_invoice()
        user, token = self.user(self.company)
        self.prepare_user(self.company, user)
        self.call(self.company, '/assignments', {'project_id': project_b, 'user_id': user})
        first = self.reused(amount='10.00', token=token)
        self.reused(invoice=invoice_b, amount='10.00', token=token)
        payment, unused = self.payment_record(amount='20.00', kind='refund',
            allocations=[(self.invoice['id'], '10.00'), (invoice_b['id'], '10.00')], token=token)
        unused, refund, unused = self.imported(payment, token=token)
        portion_a = self.rportion(refund, document_id=self.invoice['id'], token=token)
        origin_a = next(value for value in self.rorigins(refund, portion=portion_a, token=token)
                        if value['origin_version'] == 'c2' and value['entry_id'] == first['entry']['id'])
        a_entry, a_command = self.rconfirmed(refund, self.rbody(refund, document_id=self.invoice['id'],
            chosen=[(origin_a, '10.00')], token=token), token=token)
        payment, unused = self.payment_record(amount='20.00',
            allocations=[(self.invoice['id'], '10.00'), (invoice_b['id'], '10.00')], token=token)
        unused, income, unused = self.imported(payment, token=token)
        income_a, income_a_command = self.cconfirmed(income, document_id=self.invoice['id'], token=token)
        # RefundB is still unbound, so only the previously accepted B capacity
        # is usable; the A portion already refers back to this same Refundevent.
        income_b, income_b_command = self.cconfirmed(income, document_id=invoice_b['id'], token=token)
        self.assertEqual(income_b['capacity_changes'], [])
        portion_b = self.rportion(refund, document_id=invoice_b['id'], token=token)
        origin_b = next(value for value in self.rorigins(refund, portion=portion_b, token=token)
                        if value['origin_version'] == 'c2' and value['entry_id'] == income_b['id'])
        b_entry, b_command = self.rconfirmed(refund, self.rbody(refund, document_id=invoice_b['id'],
            chosen=[(origin_b, '10.00')], token=token), token=token)
        self.assertEqual(self.rstate(refund, token=token)['origin_documented_amount'], '20.00')
        self.assertEqual(len(self.call(self.company, PREFIX + refund['id'] + '/history', token=token).json['items']), 2)
        self.assertEqual(len(self.call(self.company, capacity.PREFIX + income['id'] + '/history', token=token).json['items']), 2)
        for path, command, entry in ((PREFIX + refund['id'], a_command, a_entry),
                (PREFIX + refund['id'], b_command, b_entry),
                (capacity.PREFIX + income['id'], income_a_command, income_a),
                (capacity.PREFIX + income['id'], income_b_command, income_b)):
            self.assertEqual(self.call(self.company, path + '/confirm', command, token=token, status=201).json, entry)
        self.call(self.company, refunds.PREFIX + refund['id'], token=token)
        self.permission(self.company, user, 'finance.read', effect='deny', scope=project_b)
        for path in (PREFIX + refund['id'], capacity.PREFIX + income['id'], refunds.PREFIX + refund['id']):
            self.call(self.company, path, token=token, status=(403, 404))
            self.call(self.company, path + '/history', token=token, status=(403, 404))

    def test_one_refund_event_can_use_r2_and_r1_for_different_whole_invoice_portions(self):
        source = self.reused(amount='10.00')
        unused_project, invoice_b = self.project_invoice()
        unused, unused_event, original_b = self.receipt_lot(invoice=invoice_b)
        payment, unused = self.payment_record(amount='10.00', kind='refund',
            allocations=[(self.invoice['id'], '5.00'), (invoice_b['id'], '5.00')])
        unused, event, unused = self.imported(payment)
        a = self.rportion(event, document_id=self.invoice['id'])
        b = self.rportion(event, document_id=invoice_b['id'])
        self.assertEqual((a['writer'], a['action']), ('r2', 'takeover_and_bind'))
        self.assertEqual((b['writer'], b['action']), ('r1', 'bind_legacy'))
        origin_a = next(value for value in self.rorigins(event, portion=a)
                        if value['origin_version'] == 'c2' and value['entry_id'] == source['entry']['id'])
        entry_a, command_a = self.rconfirmed(event, self.rbody(event, document_id=self.invoice['id'], chosen=[(origin_a, '5.00')]))
        legacy = next(value for value in self.portions(event) if value['document_id'] == invoice_b['id'])
        origin_b = next(value for value in self.origins(event, portion=legacy) if value['entry_id'] == original_b['id'])
        entry_b, command_b = self.confirmed(event, self.body(event, portion=legacy, chosen=[(origin_b, '5.00')]))
        state = self.rstate(event)
        self.assertEqual((state['origin_documented_amount'], state['origin_unresolved_amount']), ('10.00', '0.00'))
        self.assertEqual(self.call(self.company, PREFIX + event['id'] + '/history').json['items'], [entry_a])
        self.assertEqual(self.call(self.company, refunds.PREFIX + event['id'] + '/history').json['items'], [entry_b])
        self.assertEqual(self.call(self.company, PREFIX + event['id'] + '/confirm', command_a, status=201).json, entry_a)
        self.assertEqual(self.call(self.company, refunds.PREFIX + event['id'] + '/confirm', command_b, status=201).json, entry_b)

    def test_global_versioned_lot_budget_rejects_stale_preview_and_never_selects_another_lot(self):
        source = self.reused(amount='10.00')
        events = [self.refund('6.00')[1] for unused in range(2)]
        commands = []
        for event in events:
            origin = next(value for value in self.rorigins(event)
                          if value['origin_version'] == 'c2' and value['entry_id'] == source['entry']['id'])
            commands.append(self.rcommand(event, self.rbody(event, chosen=[(origin, '6.00')])))
        accepted = self.call(self.company, PREFIX + events[0]['id'] + '/confirm', commands[0], status=201).json
        before = self.database()
        rejected = self.call(self.company, PREFIX + events[1]['id'] + '/confirm', commands[1], status=409)
        self.assertEqual(rejected.json.get('request_resolution'), 'not_accepted')
        self.assertEqual(self.database(), before)
        remaining = next(value for value in self.rorigins(events[1])
                         if value['origin_version'] == 'c2' and value['entry_id'] == source['entry']['id'])
        self.assertEqual(remaining['remaining_amount'], '4.00')
        body = self.rbody(events[1], chosen=[(remaining, '6.00')])
        self.call(self.company, PREFIX + events[1]['id'] + '/preview', body, status=409)
        self.assertEqual(self.database(), before)
        self.assertEqual(self.call(self.company, PREFIX + events[0]['id'] + '/confirm', commands[0], status=201).json, accepted)

    def test_actual_origin_cash_date_filters_future_c2_lots_without_blocking_other_r2_clarification(self):
        source = self.reused(origin_date='2026-11-03')
        unused, early = self.refund('10.00', cash_date='2026-11-02')
        early_origins = self.rorigins(early)
        self.assertFalse(any(value['origin_version'] == 'c2' and value['entry_id'] == source['entry']['id'] for value in early_origins))
        unused, later = self.refund('10.00', cash_date='2026-11-03')
        origin = next(value for value in self.rorigins(later)
                      if value['origin_version'] == 'c2' and value['entry_id'] == source['entry']['id'])
        before = self.database()
        self.call(self.company, PREFIX + early['id'] + '/preview', self.rbody(early, chosen=[(origin, '10.00')]), status=409)
        self.assertEqual(self.database(), before)
        self.rconfirmed(later, self.rbody(later, chosen=[(origin, '10.00')]))
        self.assertEqual(self.rstate(early)['origin_unresolved_amount'], '10.00')

    def test_verified_tls_and_strict_versioned_origin_request_contract_are_read_only(self):
        self.reused()
        unused, event = self.refund('10.00')
        path = PREFIX + event['id']
        body = self.rbody(event)
        before = self.database()
        self.call(self.company, path + '/preview', body)
        invalid = [{**body, 'unknown': True}, {**body, 'origins': body['origins'] * 2},
                   {**body, 'action': 'bind_legacy'}]
        for version in (None, True, 1, 'c3', 'C2'):
            invalid.append({**body, 'origins': [{**body['origins'][0], 'origin_version': version}]})
        invalid.append({**body, 'origins': [{key: value for key, value in body['origins'][0].items() if key != 'origin_version'}]})
        for candidate in invalid:
            self.call(self.company, path + '/preview', candidate, status=400)
        for suffix in ('?unknown=1', '/history?limit=1&limit=2', '/portions?offset=-1',
                       '/origins', '/origins?portion_id=' + body['portion_id'] + '&limit=101'):
            self.call(self.company, path + suffix, status=400)
        self.call(self.company, path, {'unknown': True}, method='GET', status=400)
        self.call(self.company, path + '/preview?unknown=1', body, status=400)
        self.call(self.company, path + '/confirm', method='GET', status=405)
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
