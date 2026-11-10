"""Real MFA/HTTP and SQL rights; provider replies are controlled originals."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import os
import tempfile
import unittest
from unittest.mock import patch
import uuid

from cryptography.fernet import Fernet

from core import Problem, canonical, digest
from business_bank_reconciliation import TABLES, restore_horizon
from business_foundation import BusinessFoundation
from online.auth import totp
from online.bank_feeds_service import BankFeeds, Config, environment_config
from online.integration_http import IntegrationHttp
from online.integration_qonto import QontoReader
from online.web import create_app
from online.test_workspace_api import WorkspaceHttpFlow
from online.test_integration_qonto import ORG, TOKEN, FROM, TO, org, page, row, response, Opener
import test_business_bank_reconciliation as bank_fixture


class BankFeedTests(WorkspaceHttpFlow, unittest.TestCase):
    def setUp(self):
        self.fixture=bank_fixture.BankTests('runTest');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.office=self.fixture.office;self.owner=self.fixture.owner
        self.office.db.executescript('''
          CREATE TABLE mfa(user_id TEXT PRIMARY KEY REFERENCES users(id),secret TEXT NOT NULL,last_step BIGINT NOT NULL DEFAULT -1,recovery TEXT NOT NULL);
          CREATE TABLE auth_challenges(token TEXT PRIMARY KEY,user_id TEXT REFERENCES users(id),credential TEXT NOT NULL,secret TEXT NOT NULL,expiry DOUBLE PRECISION NOT NULL,failures INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE login_limits(key TEXT PRIMARY KEY,failures INTEGER NOT NULL,reset_at DOUBLE PRECISION NOT NULL);
        ''')
        self.config=Config(ORG,self.fixture.account['id'],TOKEN)
        self.opener=Opener(response(org()),response(page([row()])),response(org()))
        self.service=BankFeeds(self.office,config=lambda:self.config,reader=QontoReader(http=IntegrationHttp('qonto',opener=self.opener)))
        self.key=Fernet.generate_key();self.app=create_app(office=self.office,key=self.key,host='office.example.test',bank_feeds=self.service)
        self.client=self.app.test_client();self.secrets={}
        self.token=self.mfa_login(self.owner['email'],'Synthetic-password-123')
        self.body=dict(updated_from=FROM,updated_to=TO)

    def read(self,status=200,token='owner'):
        return self.call('POST','/bank-feeds/qonto/read',self.body,status=status,token=token)

    def test_actual_mfa_read_has_exact_cent_and_no_cash_bank_or_ledger_mutation(self):
        original=self.opener.open
        def outside_transaction(request,**kwargs):
            self.assertFalse(self.office.db.in_transaction)
            self.assertFalse(self.office.lock._is_owned())
            return original(request,**kwargs)
        self.opener.open=outside_transaction
        before=restore_horizon(self.office)
        tables={t:list(map(tuple,self.office.db.execute('SELECT * FROM '+t))) for t in TABLES}
        status=self.call('GET','/bank-feeds/qonto/status').json
        self.assertTrue(status['configured']);self.assertNotIn(TOKEN,json.dumps(status))
        result=self.read().json
        self.assertEqual(result['items'][0]['signed_amount_cents'],-43)
        self.assertEqual(result['local_account_id'],self.fixture.account['id'])
        self.assertEqual(before,restore_horizon(self.office))
        self.assertEqual(tables,{t:list(map(tuple,self.office.db.execute('SELECT * FROM '+t))) for t in TABLES})
        self.assertIn('qonto_read_only',self.call('GET','/business/capabilities').json['features'])

    def test_denied_role_offline_and_malformed_inputs_do_not_call_provider(self):
        tech=self.fixture.fixture.tech
        token=self.mfa_login(tech['email'],'Synthetic-password-123')
        self.read(status=403,token=token)
        self.call('GET','/bank-feeds/qonto/status',token=token,status=403)
        offline=self.call('POST','/business/offline/access',{},status=201).json['token']
        self.read(status=403,token=offline)
        for path in ('/bank-feeds/qonto/read?iban=OTHER','/bank-feeds/qonto/read?token=SECRET'):
            self.call('POST',path,self.body,status=400)
        self.call('POST','/bank-feeds/qonto/read',dict(self.body,token='SECRET'),status=400)
        self.call('GET','/bank-feeds/qonto/status?extra=1',status=400)
        self.call('GET','/bank-feeds/qonto/read',status=405)
        self.call('POST','/bank-feeds/qonto/read','{"updated_from":"2026-11-01T00:00:00Z","updated_from":"2026-11-02T00:00:00Z","updated_to":"2026-11-03T00:00:00Z"}',mime='application/json',status=400)
        self.call('GET','/bank-feeds/qonto/status',body='{}',mime='application/json',status=400)
        self.assertEqual(self.opener.requests,[])

    def test_fresh_revocation_during_provider_io_discloses_no_rows(self):
        actor=self.fixture.fixture.other_actor
        foundation=BusinessFoundation(self.office)
        foundation.save_grant(self.owner,self.fixture.req(user_id=actor['id'],permission='bank.read',scope='*',effect='allow',revision=0))
        token=self.mfa_login(actor['email'],'Synthetic-password-123')
        original=self.opener.open
        def revoke(request,**kwargs):
            value=original(request,**kwargs)
            if len(self.opener.requests)==2:
                foundation.save_grant(self.owner,self.fixture.req(user_id=actor['id'],permission='bank.read',scope='*',effect='deny',revision=1))
            return value
        self.opener.open=revoke
        result=self.read(status=403,token=token).json
        self.assertNotIn('items',result);self.assertNotIn('PRIVATE_',json.dumps(result));self.assertNotIn(TOKEN,json.dumps(result))

    def test_session_logout_rotation_and_account_rebinding_during_io_fail_closed(self):
        for change,expected in (('logout',401),('rotate',409),('binding',409)):
            with self.subTest(change=change):
                # Each scenario has an independent actual MFA/database fixture.
                if change!='logout':
                    self.tearDown();self.doCleanups();self.setUp()
                original=self.opener.open
                def mutate(request,**kwargs):
                    value=original(request,**kwargs)
                    if len(self.opener.requests)==2:
                        if change=='logout':
                            self.office.db.execute('DELETE FROM sessions WHERE token=?',(digest(self.token),))
                            self.office.db.commit()
                        elif change=='rotate':self.config=replace(self.config,token=TOKEN+'ROTATED')
                        else:
                            body=self.fixture.account_body(revision=1,label='Changed while reading',reason='Synthetic explicit change')
                            self.fixture.bank.save_account(self.owner,body)
                    return value
                self.opener.open=mutate
                self.read(status=expected)

    def test_unconfigured_and_bad_config_never_look_connected(self):
        self.config=None
        self.assertFalse(self.call('GET','/bank-feeds/qonto/status').json['configured'])
        self.read(status=409)
        self.assertEqual(self.opener.requests,[])
        self.assertNotIn(TOKEN,repr(Config(ORG,'a'*32,TOKEN)))

    def test_new_browser_asset_is_actually_served_and_private_api_is_not_cached(self):
        response=self.client.get('/office/qonto-readonly.js',base_url='https://office.example.test')
        self.assertEqual(response.status_code,200)
        self.assertIn(b'export function qontoReadUi',response.data)
        status=self.call('GET','/bank-feeds/qonto/status')
        self.assertIn('no-store',status.headers.get('Cache-Control',''))

    def test_operator_file_must_be_private_regular_absolute_and_reloaded(self):
        names=('SMARTPLAN_QONTO_ORGANIZATION_ID','SMARTPLAN_QONTO_ACCOUNT_ID','SMARTPLAN_QONTO_TOKEN_FILE')
        with tempfile.TemporaryDirectory() as directory:
            file=Path(directory)/'token';file.write_text(TOKEN+'\n');file.chmod(0o600)
            values=dict(zip(names,(ORG,self.fixture.account['id'],str(file))))
            with patch.dict(os.environ,values):
                self.assertEqual(environment_config().token,TOKEN)
                file.write_text(TOKEN+'ROTATED');self.assertEqual(environment_config().token,TOKEN+'ROTATED')
                file.chmod(0o644)
                with self.assertRaises(Problem):environment_config()
                file.chmod(0o600);link=Path(directory)/'symlink';link.symlink_to(file)
                with patch.dict(os.environ,{names[2]:str(link)}):
                    with self.assertRaises(Problem):environment_config()


if __name__=='__main__':unittest.main()
