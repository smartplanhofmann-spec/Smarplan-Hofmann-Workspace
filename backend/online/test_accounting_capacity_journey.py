"""Independent capacity journeys over verified HTTPS and real password/TOTP.

Saved legacy SQLite invoices are explicitly synthetic. Authentication, full
source authorization, financial state and the production issuer gates are not
patched. No bank, provider or non-test database is contacted.
"""
import http.client
import socket
import ssl
import unittest
import uuid

import business_schema
from online import test_accounting_refunds_journey as refunds
from online import test_accounting_components_journey as components


PREFIX = '/business/accounting/components/v2/events/'
request = refunds.request
STATE_FIELDS = {'event_id', 'source_hash', 'revision', 'state_hash', 'source_kind',
    'amount', 'currency', 'cash_date', 'documented_amount', 'undocumented_amount',
    'unallocated_amount', 'eligible', 'blocked_reason', 'writes_allowed',
    'scope', 'tax_status', 'tax_result_available'}
GROUP_FIELDS = {'group_id', 'rate', 'category', 'reason', 'archive', 'current_capacity',
    'pending_returns', 'offered_capacity', 'transition', 'group_state_hash'}


class AccountingCapacityJourneyTests(unittest.TestCase):
    base_setup = refunds.AccountingRefundsJourneyTests.base_setup
    setUp = refunds.AccountingRefundsJourneyTests.setUp
    new_company = refunds.AccountingRefundsJourneyTests.new_company
    open_app = refunds.AccountingRefundsJourneyTests.open_app
    call = refunds.AccountingRefundsJourneyTests.call
    login = refunds.AccountingRefundsJourneyTests.login
    user = refunds.AccountingRefundsJourneyTests.user
    permission = refunds.AccountingRefundsJourneyTests.permission
    account_record = refunds.AccountingRefundsJourneyTests.account_record
    source = refunds.AccountingRefundsJourneyTests.source
    import_body = refunds.AccountingRefundsJourneyTests.import_body
    prepare_user = refunds.AccountingRefundsJourneyTests.prepare_user
    payment_record = refunds.AccountingRefundsJourneyTests.payment_record
    project_invoice = refunds.AccountingRefundsJourneyTests.project_invoice
    open_item = refunds.AccountingRefundsJourneyTests.open_item
    database = refunds.AccountingRefundsJourneyTests.database
    allocate = refunds.AccountingRefundsJourneyTests.allocate
    imported = refunds.AccountingRefundsJourneyTests.imported
    component = refunds.AccountingRefundsJourneyTests.component
    receipt_lot = refunds.AccountingRefundsJourneyTests.receipt_lot
    refund = refunds.AccountingRefundsJourneyTests.refund
    state = refunds.AccountingRefundsJourneyTests.state
    portions = refunds.AccountingRefundsJourneyTests.portions
    origins = refunds.AccountingRefundsJourneyTests.origins
    body = refunds.AccountingRefundsJourneyTests.body
    command = refunds.AccountingRefundsJourneyTests.command
    confirmed = refunds.AccountingRefundsJourneyTests.confirmed
    source_rows = refunds.AccountingRefundsJourneyTests.source_rows

    def replacement(self, amount, *, token='owner', cash_date='2026-11-02'):
        payment, unused = self.payment_record(amount=amount,
            allocations=[(self.invoice['id'], amount)], token=token)
        unused_source, event, unused_command = self.imported(payment, token=token, cash_date=cash_date)
        return payment, event

    def cstate(self, event, *, token='owner'):
        value = self.call(self.company, PREFIX + event['id'], token=token).json
        self.assertEqual(set(value), STATE_FIELDS)
        return value

    def cportion(self, event, *, token='owner'):
        values = self.call(self.company, PREFIX + event['id'] + '/portions', token=token).json
        self.assertEqual(set(values), {'items', 'total', 'next_offset', 'scope'})
        self.assertEqual(len(values['items']), 1)
        portion = values['items'][0]
        for group in portion['groups']:
            self.assertEqual(set(group), GROUP_FIELDS)
            self.assertEqual(set(group['archive']), {'net', 'tax', 'gross'})
            self.assertEqual(set(group['pending_returns']), {'net', 'tax', 'gross', 'not_before_date'})
            for key in ('current_capacity', 'offered_capacity'):
                self.assertEqual(set(group[key]), {'segment_id', 'net', 'tax', 'gross', 'not_before_date'})
        return portion

    def cbody(self, event, *, token='owner'):
        state, portion = self.cstate(event, token=token), self.cportion(event, token=token)
        self.assertEqual(len(portion['groups']), 1)
        return dict(source_hash=state['source_hash'], expected_revision=state['revision'],
            state_hash=state['state_hash'], portion_id=portion['portion_id'],
            portion_state_hash=portion['portion_state_hash'], action=portion['action'],
            groups=[dict(group_id=portion['groups'][0]['group_id'], amount=portion['amount'])],
            reason='Synthetic explicit capacity reuse after verified refund')

    def ccommand(self, event, body=None, *, token='owner'):
        body = self.cbody(event, token=token) if body is None else body
        preview = self.call(self.company, PREFIX + event['id'] + '/preview', body, token=token).json
        return request(**body, preview_hash=preview['preview_hash'], confirmation=True)

    def cconfirmed(self, event, *, token='owner'):
        command = self.ccommand(event, token=token)
        entry = self.call(self.company, PREFIX + event['id'] + '/confirm', command,
                          token=token, status=201).json
        return entry, command

    def bind(self, event, component, amount, *, token='owner'):
        origin = next(value for value in self.origins(event, token=token) if value['entry_id'] == component['id'])
        return self.confirmed(event, self.body(event, chosen=[(origin, amount)], token=token), token=token)

    def test_middle_lot_and_successor_preserve_actual_original_cents_without_rewriting_c1_r1(self):
        lots = [self.receipt_lot(amount) for amount in ('39.67', '39.67', '39.66')]
        self.assertEqual([(value['net'], value['tax']) for unused, unused_event, value in lots],
                         [('33.34', '6.33'), ('33.33', '6.34'), ('33.33', '6.33')])
        unused, first_refund = self.refund('39.67')
        returned, return_command = self.bind(first_refund, lots[1][2], '39.67')
        unused, first = self.replacement('26.44')
        portion = self.cportion(first)
        self.assertEqual((portion['writer'], portion['action']), ('c2', 'takeover_and_document'))
        offered = portion['groups'][0]['offered_capacity']
        self.assertEqual((offered['net'], offered['tax'], offered['gross']), ('33.33', '6.34', '39.67'))
        before, old_op = self.source_rows(), self.open_item(self.invoice)
        entry, command = self.cconfirmed(first)
        self.assertEqual((entry['net'], entry['tax']), ('22.21', '4.23'))
        self.assertEqual(self.source_rows(), before)
        self.assertEqual(self.open_item(self.invoice), old_op)
        unused, second_refund = self.refund('13.22')
        second_returned, second_return_command = self.bind(second_refund, lots[0][2], '13.22')
        unused, second = self.replacement('26.45')
        next_portion = self.cportion(second)
        group = next_portion['groups'][0]
        self.assertEqual(group['transition'], 'successor')
        self.assertEqual((group['current_capacity']['net'], group['current_capacity']['tax'], group['current_capacity']['gross']),
                         ('11.12', '2.11', '13.23'))
        self.assertEqual((group['offered_capacity']['net'], group['offered_capacity']['tax'], group['offered_capacity']['gross']),
                         ('22.23', '4.22', '26.45'))
        before, old_op = self.source_rows(), self.open_item(self.invoice)
        following, next_command = self.cconfirmed(second)
        self.assertEqual((following['net'], following['tax']), ('22.23', '4.22'))
        self.assertNotEqual(entry['lines'][0]['segment_id'], following['lines'][0]['segment_id'])
        self.assertEqual(self.source_rows(), before)
        self.assertEqual(self.open_item(self.invoice), old_op)
        for event, expected, original in ((first, entry, command), (second, following, next_command)):
            self.assertEqual(self.call(self.company, PREFIX + event['id'] + '/confirm', original, status=201).json, expected)
            state = self.cstate(event)
            self.assertEqual((state['documented_amount'], state['undocumented_amount']), (event['amount'], '0.00'))
            self.assertEqual(state['tax_status'], 'unconfigured')
            self.assertFalse(state['tax_result_available'])
        for event, expected, original in ((first_refund, returned, return_command),
                                          (second_refund, second_returned, second_return_command)):
            self.assertEqual(self.call(self.company, refunds.PREFIX + event['id'] + '/confirm', original, status=201).json, expected)
            self.assertFalse(expected['capacity_released'])
        for unused, event, original in lots:
            self.assertEqual(self.call(self.company, components.PREFIX + event['id'] + '/history').json['items'], [original])

    def test_unimported_and_unbound_finance_refunds_gate_new_release_but_not_existing_capacity(self):
        unused, unused_event, original = self.receipt_lot()
        payment, unused = self.payment_record(amount='39.67', kind='refund', allocations=[(self.invoice['id'], '39.67')])
        unused, receipt = self.replacement('10.00')
        portion = self.cportion(receipt)
        self.assertEqual(portion['pending_blocked_reason'], 'refund_origin_unresolved')
        self.assertFalse(portion['eligible'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_accounting_capacity_releases').fetchone()[0], 0)
        unused, refund, unused = self.imported(payment)
        self.assertEqual(self.cportion(receipt)['pending_blocked_reason'], 'refund_origin_unresolved')
        self.bind(refund, original, '39.67')
        self.assertEqual(self.cportion(receipt)['refund_status'], 'clear')
        self.cconfirmed(receipt)
        # A later real Finance refund is deliberately not imported or bound yet.
        self.payment_record(amount='5.00', kind='refund', allocations=[(self.invoice['id'], '5.00')])
        unused, second = self.replacement('5.00')
        portion = self.cportion(second)
        self.assertEqual(portion['writer'], 'c2')
        self.assertEqual(portion['action'], 'document_current')
        self.assertEqual(portion['pending_blocked_reason'], 'refund_origin_unresolved')
        self.assertTrue(portion['eligible'])
        self.assertEqual(portion['groups'][0]['current_capacity']['gross'], '29.67')
        self.assertEqual(portion['groups'][0]['transition'], 'none')
        releases = self.office.db.execute('SELECT COUNT(*) FROM business_accounting_capacity_releases').fetchone()[0]
        self.cconfirmed(second)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_accounting_capacity_releases').fetchone()[0], releases)

    def test_later_origin_scope_extension_hides_bound_history_and_replays(self):
        project_b, invoice_b = self.project_invoice()
        user, token = self.user(self.company)
        self.prepare_user(self.company, user)
        self.call(self.company, '/assignments', {'project_id': project_b, 'user_id': user})
        payment, unused = self.payment_record(amount='149.00', allocations=[(self.invoice['id'], '119.00')], token=token)
        unused, origin, unused = self.imported(payment, token=token)
        original = self.component(origin, token=token)
        unused, refund = self.refund('20.00', token=token)
        self.bind(refund, original, '20.00', token=token)
        unused, receipt = self.replacement('10.00', token=token)
        entry, command = self.cconfirmed(receipt, token=token)
        self.allocate(payment, invoice_b, '30.00', token=token)
        self.permission(self.company, user, 'finance.read', effect='deny', scope=project_b)
        for suffix, body in (('', None), ('/history', None), ('/portions', None), ('/confirm', command)):
            self.call(self.company, PREFIX + receipt['id'] + suffix, body, token=token, status=(403, 404))
        self.permission(self.company, user, 'finance.read', scope=project_b, revision=1)
        self.assertEqual(self.call(self.company, PREFIX + receipt['id'] + '/confirm', command, token=token, status=201).json, entry)
        self.permission(self.company, user, 'finance.write', effect='deny', scope=project_b)
        self.assertFalse(self.cstate(receipt, token=token)['writes_allowed'])
        self.call(self.company, PREFIX + receipt['id'] + '/history', token=token)
        self.call(self.company, PREFIX + receipt['id'] + '/confirm', command, token=token, status=403)

    def test_unconsumed_group_in_historical_portion_retains_its_full_source_rights(self):
        self.invoice = components.AccountingComponentsJourneyTests.invoice_with_groups(self)
        project_b, invoice_b = self.project_invoice()
        user, token = self.user(self.company)
        self.prepare_user(self.company, user)
        self.call(self.company, '/assignments', {'project_id': project_b, 'user_id': user})
        lots = []
        for rate, amount, total in (('19', '119.00', '119.00'), ('7', '53.50', '63.50')):
            payment, unused = self.payment_record(amount=total, allocations=[(self.invoice['id'], amount)], token=token)
            unused, event, unused = self.imported(payment, token=token)
            path = components.PREFIX + event['id']
            state = self.call(self.company, path, token=token).json
            portion = self.call(self.company, path + '/portions', token=token).json['items'][0]
            group = next(value for value in portion['groups'] if value['rate'] == rate)
            body = dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
                portion_id=portion['portion_id'], portion_state_hash=portion['portion_state_hash'],
                groups=[dict(group_id=group['group_id'], amount=amount)], reason='Synthetic separate origin group')
            preview = self.call(self.company, path + '/preview', body, token=token).json
            entry = self.call(self.company, path + '/confirm', request(**body, preview_hash=preview['preview_hash'],
                confirmation=True), token=token, status=201).json
            lots.append((payment, entry))
        for unused_payment, origin in lots:
            unused, refund = self.refund('10.00', token=token)
            self.bind(refund, origin, '10.00', token=token)
        accepted = []
        for unused in range(2):
            unused_payment, event = self.replacement('5.00', token=token)
            state, portion = self.cstate(event, token=token), self.cportion(event, token=token)
            group = next(value for value in portion['groups'] if value['rate'] == '19')
            body = dict(source_hash=state['source_hash'], expected_revision=state['revision'], state_hash=state['state_hash'],
                portion_id=portion['portion_id'], portion_state_hash=portion['portion_state_hash'], action=portion['action'],
                groups=[dict(group_id=group['group_id'], amount='5.00')], reason='Synthetic only standard group consumed')
            command = self.ccommand(event, body, token=token)
            entry = self.call(self.company, PREFIX + event['id'] + '/confirm', command, token=token, status=201).json
            accepted.append((event, command, entry))
        event, command, entry = accepted[-1]
        self.assertEqual(entry['capacity_changes'], [])
        self.assertEqual(len(entry['lines']), 1)
        self.assertEqual(next(group for group in entry['portion']['groups'] if group['rate'] == '7')['current_capacity']['gross'], '10.00')
        # Group7 has no line or new segment in this entry, but its historical
        # public portion and carried capacity still depend on the earlier source.
        self.allocate(lots[1][0], invoice_b, '10.00', token=token)
        self.permission(self.company, user, 'finance.read', effect='deny', scope=project_b)
        for suffix, body in (('', None), ('/history', None), ('/portions', None), ('/confirm', command)):
            self.call(self.company, PREFIX + event['id'] + suffix, body, token=token, status=(403, 404))
        self.permission(self.company, user, 'finance.read', scope=project_b, revision=1)
        self.assertEqual(self.call(self.company, PREFIX + event['id'] + '/confirm', command, token=token, status=201).json, entry)

    def test_current_shared_segment_invalidates_pending_preview_without_changing_accepted_receipts(self):
        unused, unused_event, original = self.receipt_lot()
        unused, refund = self.refund('39.67')
        self.bind(refund, original, '39.67')
        first, second = [self.replacement('10.00')[1] for unused in range(2)]
        commands = [self.ccommand(event) for event in (first, second)]
        accepted = self.call(self.company, PREFIX + first['id'] + '/confirm', commands[0], status=201).json
        before = self.database()
        rejected = self.call(self.company, PREFIX + second['id'] + '/confirm', commands[1], status=409)
        self.assertEqual(rejected.json.get('request_resolution'), 'not_accepted')
        self.assertEqual(self.database(), before)
        current, unused = self.cconfirmed(second)
        self.assertEqual(current['action'], 'document_current')
        self.assertEqual(self.call(self.company, PREFIX + first['id'] + '/confirm', commands[0], status=201).json, accepted)
        self.call(self.company, PREFIX + first['id'] + '/confirm', {**commands[0], 'request_id': uuid.uuid4().hex}, status=409)
        business_schema.set_mode(self.office, 'legacy')
        gated = self.call(self.company, PREFIX + first['id'] + '/confirm', commands[0], status=409)
        self.assertNotIn('request_resolution', gated.json)
        business_schema.set_mode(self.office, 'business')
        self.assertEqual(self.call(self.company, PREFIX + first['id'] + '/confirm', commands[0], status=201).json, accepted)

    def test_new_finance_refund_between_preview_and_confirmation_prevents_first_handoff(self):
        unused, unused_event, original = self.receipt_lot()
        unused, refund = self.refund('20.00')
        self.bind(refund, original, '20.00')
        unused, event = self.replacement('10.00')
        command = self.ccommand(event)
        self.payment_record(amount='5.00', kind='refund', allocations=[(self.invoice['id'], '5.00')])
        before = self.database()
        self.call(self.company, PREFIX + event['id'] + '/confirm', command, status=409)
        self.assertEqual(self.database(), before)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_accounting_capacity_handoffs').fetchone()[0], 0)
        self.assertEqual(self.cportion(event)['pending_blocked_reason'], 'refund_origin_unresolved')

    def test_receipt_date_cannot_spend_later_return_cents_and_invalid_input_is_read_only(self):
        unused, unused_event, original = self.receipt_lot(cash_date='2026-10-30')
        unused, refund = self.refund('20.00', cash_date='2026-11-02')
        self.bind(refund, original, '20.00')
        unused, early = self.replacement('10.00', cash_date='2026-11-01')
        portion = self.cportion(early)
        self.assertFalse(portion['eligible'])
        self.assertEqual(portion['pending_blocked_reason'], 'receipt_before_capacity')
        unused, current = self.replacement('10.00', cash_date='2026-11-02')
        body = self.cbody(current)
        before = self.database()
        for amount in ('0.00', '-1.00', '10', '10.001', '1e1', 10, True):
            bad = {**body, 'groups': [{**body['groups'][0], 'amount': amount}]}
            self.call(self.company, PREFIX + current['id'] + '/preview', bad, status=400)
        for changes in ({'expected_revision': True}, {'action': 'document_legacy'}, {'groups': []},
                        {'groups': body['groups'] * 2}, {'reason': 'two\nlines'}):
            self.call(self.company, PREFIX + current['id'] + '/preview', {**body, **changes}, status=400)
        self.assertEqual(self.database(), before)
        self.cconfirmed(current)

    def test_verified_tls_strict_query_and_authenticated_capacity_contract(self):
        unused, unused_event, original = self.receipt_lot()
        unused, refund = self.refund('20.00')
        self.bind(refund, original, '20.00')
        unused, event = self.replacement('10.00')
        path = PREFIX + event['id']
        body = self.cbody(event)
        before = self.database()
        self.call(self.company, path + '/preview', body)
        self.assertEqual(self.database(), before)
        for suffix in ('?unknown=1', '/portions?limit=1&limit=2', '/history?offset=-1', '/portions?limit=101'):
            self.call(self.company, path + suffix, status=400)
        self.call(self.company, path, {'unexpected': True}, method='GET', status=400)
        self.call(self.company, path + '/preview?unknown=1', body, status=400)
        self.call(self.company, path + '/preview', {**body, 'unknown': True}, status=400)
        self.call(self.company, path + '/confirm', method='GET', status=405)
        self.assertEqual(self.database(), before)
        self.call(self.company, path, token=None, status=401)
        for context, hostname in ((ssl.create_default_context(), self.company['host']),
                                  (self.company['tls'], 'other.example.test')):
            with self.assertRaises(ssl.SSLCertVerificationError):
                with socket.create_connection(('127.0.0.1', self.company['server'].server_port), timeout=5) as raw:
                    with context.wrap_socket(raw, server_hostname=hostname):
                        self.fail('Untrusted CA or certificate hostname was accepted')
        with socket.create_connection(('127.0.0.1', self.company['server'].server_port), timeout=5) as raw:
            with self.company['tls'].wrap_socket(raw, server_hostname=self.company['host']) as connection:
                connection.sendall(('GET /api/v1' + path + ' HTTP/1.1\r\nHost: other.example.test\r\n'
                    'Connection: close\r\nAuthorization: Bearer ' + self.company['token'] + '\r\n\r\n').encode('ascii'))
                response = http.client.HTTPResponse(connection); response.begin()
                self.assertEqual(response.status, 400)
                response.read()

    def test_empty_segment_does_not_carry_a_later_date_into_an_independently_earlier_return(self):
        unused, unused_event, original = self.receipt_lot(cash_date='2026-10-30')
        unused, first_refund = self.refund('20.00', cash_date='2026-11-02')
        self.bind(first_refund, original, '20.00')
        unused, first = self.replacement('20.00', cash_date='2026-11-02')
        entry, command = self.cconfirmed(first)
        self.assertEqual(entry['lines'][0]['remaining_gross'], '0.00')
        # Arrival order differs from explicit cash dates. The first returned
        # capacity is exhausted; this new return has its own earlier date.
        unused, earlier_refund = self.refund('10.00', cash_date='2026-11-01')
        self.bind(earlier_refund, original, '10.00')
        unused, earlier_receipt = self.replacement('10.00', cash_date='2026-11-01')
        portion = self.cportion(earlier_receipt)
        self.assertTrue(portion['eligible'])
        self.assertEqual(portion['groups'][0]['offered_capacity']['not_before_date'], '2026-11-01')
        self.cconfirmed(earlier_receipt)
        self.assertEqual(self.call(self.company, PREFIX + first['id'] + '/confirm', command, status=201).json, entry)


if __name__ == '__main__':
    unittest.main()
