"""Own-company API key follows Qonto's exact primary contract, never Basic."""
from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core import Problem
from business_bank_reconciliation import restore_horizon
from online.bank_feeds_service import Config, environment_config
from online.integration_http import IntegrationHttp
from online.integration_qonto import QontoReader
from online.test_integration_qonto import ORG, IBAN, FROM, TO, org, page, row, response, Opener
from online import test_bank_feeds_service as bank_tests

LOGIN='synthetic-own-company-1234'
KEY='SYNTHETIC_OWN_ACCOUNT_SECRET_KEY'


def organization():
    value=org();value['organization']['slug']=LOGIN;return value


class OwnAccountTests(unittest.TestCase):
    def test_exact_key_header_fixed_get_no_basic_or_bearer_and_no_secret_in_result(self):
        opener=Opener(response(organization()),response(page([row()])),response(organization()))
        result=QontoReader(http=IntegrationHttp('qonto',opener=opener)).collect(token=KEY,auth_mode='own_account_api_key',login=LOGIN,organization_id=ORG,iban=IBAN,updated_from=FROM,updated_to=TO)
        self.assertEqual(result['items'][0]['signed_amount_cents'],-43)
        for request,_ in opener.requests:
            self.assertEqual(request.get_header('Authorization'),LOGIN+':'+KEY)
            self.assertNotIn(KEY,request.full_url);self.assertEqual(request.get_method(),'GET')
        self.assertNotIn(KEY,json.dumps(result))

    def test_mode_never_inferred_and_credential_syntax_is_rejected_before_io(self):
        for mode,login,key in [('invented',LOGIN,KEY),('own_account_api_key',None,KEY),('own_account_api_key','wrong:login',KEY),('own_account_api_key',LOGIN,KEY+'\r\nX-Test:x'),('oauth_access_token',LOGIN,KEY)]:
            opener=Opener()
            with self.subTest(mode=mode,login=login):
                with self.assertRaises(Problem) as caught:QontoReader(http=IntegrationHttp('qonto',opener=opener)).collect(token=key,auth_mode=mode,login=login,organization_id=ORG,iban=IBAN,updated_from=FROM,updated_to=TO)
                self.assertEqual(caught.exception.status,409);self.assertEqual(opener.requests,[])

    def test_api_key_does_not_bypass_the_expected_authenticated_organization(self):
        value=organization();value['organization']['id']='aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
        with self.assertRaises(Problem):QontoReader(http=IntegrationHttp('qonto',opener=Opener(response(value)))).collect(token=KEY,auth_mode='own_account_api_key',login=LOGIN,organization_id=ORG,iban=IBAN,updated_from=FROM,updated_to=TO)

    def test_private_file_explicit_mode_and_sign_in_are_reloaded_without_repr_leak(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'key';path.write_text(KEY);path.chmod(0o600)
            values=dict(SMARTPLAN_QONTO_ORGANIZATION_ID=ORG,SMARTPLAN_QONTO_ACCOUNT_ID='a'*32,SMARTPLAN_QONTO_TOKEN_FILE=str(path),SMARTPLAN_QONTO_AUTH_MODE='own_account_api_key',SMARTPLAN_QONTO_LOGIN=LOGIN)
            with patch.dict(os.environ,values):
                config=environment_config();self.assertEqual(config.auth_mode,'own_account_api_key');self.assertEqual(config.login,LOGIN)
                self.assertNotIn(KEY,repr(config));self.assertNotIn(LOGIN,repr(config))
                path.write_text(KEY+'ROTATED');self.assertNotEqual(config,environment_config())
                with patch.dict(os.environ,{'SMARTPLAN_QONTO_AUTH_MODE':'oauth_access_token'}):
                    with self.assertRaises(Problem):environment_config()

    def test_real_mfa_api_status_read_and_login_rotation_preserve_existing_bank_state(self):
        fixture=bank_tests.BankFeedTests('runTest')
        try:
            fixture.setUp();fixture.config=Config(ORG,fixture.fixture.account['id'],KEY,auth_mode='own_account_api_key',login=LOGIN)
            fixture.opener.responses=[response(organization()),response(page([row()])),response(organization())]
            status=fixture.call('GET','/bank-feeds/qonto/status').json
            self.assertEqual(status['authentication'],'operator_own_account_api_key');self.assertNotIn(KEY,json.dumps(status));self.assertNotIn(LOGIN,json.dumps(status))
            original_bank=restore_horizon(fixture.office)
            fixture.read()
            self.assertEqual(original_bank,restore_horizon(fixture.office))
            fixture.opener.requests.clear();fixture.opener.responses=[response(organization()),response(page([row()])),response(organization())]
            original=fixture.opener.open
            def mutate(request,**kwargs):
                result=original(request,**kwargs)
                if len(fixture.opener.requests)==2:fixture.config=replace(fixture.config,login=LOGIN+'-changed')
                return result
            fixture.opener.open=mutate
            rejected=fixture.read(status=409).json;self.assertNotIn('items',rejected);self.assertNotIn(KEY,json.dumps(rejected))
            self.assertEqual(original_bank,restore_horizon(fixture.office))
        finally:fixture.doCleanups()


if __name__=='__main__':unittest.main()
