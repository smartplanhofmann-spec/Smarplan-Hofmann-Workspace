"""Explicit synthetic upstream; real Flask/MFA/rights and Qonto parser remain."""
import json
from urllib.parse import urlsplit, parse_qs

from business_accounting import Accounting
from business_bank_reconciliation import BankReconciliation
from online.bank_feeds_service import BankFeeds, Config
from online.integration_qonto import QontoReader
from online.integration_http import IntegrationHttp
from online.test_integration_http import Response
from online.test_integration_qonto import ORG, TOKEN, IBAN, org, row, page


def seed_qonto(office, metadata, *, own_key=False):
    import uuid
    actor=dict(office.db.execute("SELECT id,role,email FROM users WHERE role='owner'").fetchone())
    def request(**values):return dict(request_id=uuid.uuid4().hex,**values)
    account=Accounting(office).create_account(actor,request(confirmation=True,code='QONTO-SYN',name='Synthetic Qonto account',kind='bank'))
    BankReconciliation(office).save_account(actor,request(account_id=account['id'],account_revision=1,revision=0,iban=IBAN,label='Synthetic Qonto',active=True,coverage_from='2026-01-01',coverage_to=None,reason=''))
    class Provider:
        def open(self, request, *, timeout):
            assert request.get_method()=='GET' and request.data is None
            assert request.get_header('Authorization')==('synthetic-company:'+TOKEN if own_key else 'Bearer '+TOKEN)
            url=urlsplit(request.full_url)
            assert url.scheme=='https' and url.netloc=='thirdparty.qonto.com'
            if url.path=='/v2/organization':value=org()
            else:
                assert url.path=='/v2/transactions' and parse_qs(url.query)['iban']==[IBAN]
                value=page([row(1),row(2,status='pending',settled_at=None,amount=5,amount_cents=500,side='credit'),row(3,status='declined'),row(4,status='reversed')])
            return Response(json.dumps(value,separators=(',',':')).encode())
    metadata['qonto_account_id']=account['id']
    return BankFeeds(office,config=lambda:Config(ORG,account['id'],TOKEN,
        auth_mode='own_account_api_key' if own_key else 'oauth_access_token',login='synthetic-company' if own_key else ''),
        reader=QontoReader(http=IntegrationHttp('qonto',opener=Provider())))
