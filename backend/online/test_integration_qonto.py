"""Independent synthetic provider pages through the real pinned HTTP transport."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import unittest
from urllib.parse import parse_qs, urlsplit
from urllib.error import HTTPError
import uuid

from core import Problem, canonical
from online.integration_http import IntegrationHttp
from online.integration_qonto import QontoReader, window
from online.test_integration_http import Opener, Response

ORG = 'cb47875a-9b12-416e-aa9a-265b9dfaeee7'
ACCOUNT = '018f71db-c635-78b5-b90a-ea05de98c2bf'
IBAN = 'DE89370400440532013000'
TOKEN = 'SYNTHETIC_SECRET_ONLY_IN_HEADER'
FROM = '2026-11-01T00:00:00Z'
TO = '2026-11-10T12:00:00Z'


def org():
    return dict(organization=dict(id=ORG, legal_name='Synthetic company',
                bank_accounts=[dict(id=ACCOUNT, iban=IBAN, currency='EUR', status='active', name='Synthetic bank',
                                    balance=123.45, balance_cents=12345, authorized_balance=120.01, authorized_balance_cents=12001,
                                    updated_at='2026-11-10T10:00:00.000Z'),
                               dict(iban='PRIVATE_OTHER_IBAN', name='PRIVATE_OTHER_ACCOUNT')]))


def row(index=1, **changes):
    return dict(id=str(uuid.UUID(int=index)), transaction_id='SYN-' + str(index), bank_account_id=ACCOUNT,
                amount=0.43, amount_cents=43, side='debit', currency='EUR', status='completed',
                label='Synthetic transfer', clean_counterparty_name='Synthetic payer', reference=None,
                settled_at='2026-11-03T08:01:12.000Z', updated_at='2026-11-04T09:00:00.000Z',
                is_external_transaction=False, note='PRIVATE_NOTE_NOT_REQUESTED', unknown_field='PRIVATE_UNKNOWN') | changes


def page(rows, number=1, count=None):
    count = len(rows) if count is None else count
    total = max(1, (count + 99) // 100)
    return dict(transactions=rows, meta=dict(current_page=number, next_page=number+1 if number < total else None,
                                           prev_page=number-1 if number>1 else None, total_count=count, total_pages=total, per_page=100))


def response(value):
    return Response(json.dumps(value, separators=(',', ':')).encode())


class QontoTests(unittest.TestCase):
    def read(self, pages=None, before=None, after=None):
        self.opener=Opener(response(before or org()), *[response(p) for p in (pages or [page([row()])])], response(after or org()))
        return QontoReader(http=IntegrationHttp('qonto', opener=self.opener)).collect(
            token=TOKEN, organization_id=ORG, iban=IBAN, updated_from=FROM, updated_to=TO)

    def error(self, status, callback):
        with self.assertRaises(Problem) as caught:
            callback()
        self.assertEqual(caught.exception.status, status, caught.exception.message)
        self.assertNotIn(TOKEN, caught.exception.message)

    def test_cent_exact_all_four_statuses_no_private_fields_and_no_financial_semantics(self):
        rows=[row(i+1, status=s, settled_at=None if s=='pending' else row()['settled_at']) for i,s in enumerate(('completed','pending','declined','reversed'))]
        result=self.read([page(rows)])
        self.assertEqual([r['status'] for r in result['items']], ['completed','pending','declined','reversed'])
        self.assertEqual([r['signed_amount_cents'] for r in result['items']], [-43]*4)
        self.assertFalse(result['complete_statement']);self.assertFalse(result['financial_changes']);self.assertFalse(result['atomic_snapshot'])
        self.assertNotIn('PRIVATE_', json.dumps(result));self.assertNotIn(TOKEN, json.dumps(result))
        payload={k:v for k,v in result.items() if k not in ('content_hash','read_at')}
        self.assertEqual(result['content_hash'],hashlib.sha256(canonical(payload).encode()).hexdigest())
        self.assertEqual(len(result['source_pages']),3)
        for request,timeout in self.opener.requests:
            self.assertEqual(request.get_header('Authorization'),'Bearer '+TOKEN)
            self.assertEqual(request.get_method(),'GET');self.assertIsNone(request.data)
            self.assertEqual(urlsplit(request.full_url).netloc,'thirdparty.qonto.com')
            self.assertNotIn(TOKEN,request.full_url);self.assertLessEqual(timeout,8)
        query=parse_qs(urlsplit(self.opener.requests[1][0].full_url).query)
        self.assertEqual(query['status[]'],['pending','declined','completed','reversed'])
        self.assertEqual(query['iban'],[IBAN]);self.assertEqual(query['updated_at_from'],[FROM])

    def test_org_without_id_in_account_example_uses_iban_and_rejects_mixed_remote_accounts(self):
        before=org();del before['organization']['bank_accounts'][0]['id']
        self.assertEqual(self.read(before=before,after=before)['items'][0]['bank_account_id'],ACCOUNT)
        self.error(503,lambda:self.read([page([row(),row(2,bank_account_id=str(uuid.uuid4()))])],before=before,after=before))

    def test_fully_consumed_pagination_zero_rows_and_upper_exclusive_boundary(self):
        result=self.read([page([row(i+1) for i in range(100)],count=101),page([row(101,updated_at=TO)],number=2,count=101)])
        self.assertEqual(result['provider_rows'],101);self.assertEqual(len(result['items']),100)
        result=self.read([page([])]);self.assertEqual(result['items'],[])
        self.assertEqual(result['account_after']['balance_cents'],12345)

    def test_foreign_org_account_currency_external_rows_and_duplicate_ids_fail_closed(self):
        for change in (dict(bank_account_id=str(uuid.uuid4())),dict(currency='USD'),dict(is_external_transaction=True),dict(status='invented'),dict(side='both'),dict(amount_cents=True),dict(amount_cents=-43),dict(amount=0.431),dict(amount=43),dict(settled_at=None),dict(updated_at='2026-10-31T00:00:00Z')):
            with self.subTest(change=change):self.error(503,lambda:self.read([page([row(**change)])]))
        self.error(503,lambda:self.read([page([row(),row()])]))
        bad=org();bad['organization']['id']=str(uuid.uuid4());self.error(503,lambda:self.read(before=bad))
        bad=org();bad['organization']['bank_accounts'][0]['currency']='USD';self.error(503,lambda:self.read(after=bad))

    def test_changed_or_incomplete_meta_never_returns_partial_data(self):
        for change in (dict(total_count=1001),dict(current_page=2),dict(next_page=1),dict(next_page=True),dict(per_page=99),dict(prev_page=0),dict(total_pages=10),dict(total_count=True)):
            bad=page([row()]);bad['meta'].update(change)
            with self.subTest(change=change):self.error(503,lambda:self.read([bad]))
        self.error(503,lambda:self.read([page([row()],count=2)]))
        first=page([row(i+1) for i in range(100)],count=101)
        self.error(409,lambda:self.read([first,page([row(101)],number=2,count=102)]))

    def test_duplicate_json_float_precision_nonfinite_and_wrong_content_types(self):
        for raw in (b'{"organization":{},"organization":{}}',b'{"organization":NaN}',b'{"organization":1e1000000000}',b'[]'):
            opener=Opener(Response(raw))
            self.error(503,lambda:QontoReader(http=IntegrationHttp('qonto',opener=opener)).collect(token=TOKEN,organization_id=ORG,iban=IBAN,updated_from=FROM,updated_to=TO))
        result=self.read([page([row(amount=9999999999999.99,amount_cents=999999999999999)])])
        self.assertEqual(result['items'][0]['signed_amount_cents'],-999999999999999)

    def test_decimal_overflow_and_subcent_originals_are_not_rounded_or_reported_as_internal_errors(self):
        for amount in ('1e1000000000','0.43000000000000001'):
            raw=json.dumps(page([row()]),separators=(',',':')).replace('"amount":0.43','"amount":'+amount).encode()
            opener=Opener(response(org()),Response(raw))
            self.error(503,lambda:QontoReader(http=IntegrationHttp('qonto',opener=opener)).collect(token=TOKEN,organization_id=ORG,iban=IBAN,updated_from=FROM,updated_to=TO))

    def test_writes_urls_token_parameters_and_redirects_are_never_followed(self):
        opener=Opener();client=IntegrationHttp('qonto',opener=opener)
        for call in (lambda:client.raw('/v2/transfers'),lambda:client.raw('https://attacker.invalid/v2/organization'),
                     lambda:client.raw('/v2/organization',method='POST'),lambda:client.raw('/v2/organization',json_body={}),
                     lambda:client.raw('/v2/transactions',params={'access_token':TOKEN}),
                     lambda:client.raw('/v2/transactions',params={'unknown':'x'})):
            self.error(400,call)
        self.assertEqual(opener.requests,[])
        opener=Opener(HTTPError('https://thirdparty.qonto.com/v2/organization',302,'SECRET',{'Location':'https://attacker.invalid'},None))
        self.error(503,lambda:QontoReader(http=IntegrationHttp('qonto',opener=opener)).collect(token=TOKEN,organization_id=ORG,iban=IBAN,updated_from=FROM,updated_to=TO))
        self.assertEqual(len(opener.requests),1)

    def test_window_and_credential_rejected_before_provider_io(self):
        for first,last in ((FROM,FROM),(TO,FROM),(FROM,'2027-01-01T00:00:00Z'),('2026-11-01',TO)):
            self.error(400,lambda:window(first,last))
        opener=Opener()
        self.error(409,lambda:QontoReader(http=IntegrationHttp('qonto',opener=opener)).collect(token=TOKEN+'\r\nHeader:x',organization_id=ORG,iban=IBAN,updated_from=FROM,updated_to=TO))
        self.assertEqual(opener.requests,[])


if __name__=='__main__':unittest.main()
