"""Independent integration review: new bank proof and immutable old EÜR facts."""
import json
import unittest

import business_schema
from business_accounting_euer import EuerAccounting,validate_integrity as validate_euer
from business_bank_reconciliation import BankReconciliation
from core import Problem,canonical
import test_business_accounting as accounting
import test_business_bank_reconciliation as bank_fixture


class BankEuerIntegrationReview(unittest.TestCase):
    def setUp(self):
        self.f=accounting.AccountingTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.office,self.owner=self.f.office,self.f.owner
        self.b=bank_fixture.BankTests('runTest');self.b.office=self.office;self.b.owner=self.owner
        self.b.fixture=self.f;self.b.account=self.f.account;self.b.bank=BankReconciliation(self.office,clock=self.f.clock)
        self.b.configure();self.euer=EuerAccounting(self.office,clock=self.f.clock)

    def period(self,period,action,revision,confirm=True):
        state=self.euer.state(self.owner)
        body=dict(operation='period',expected_revision=state['revision'],state_hash=state['state_hash'],reason='Independent synthetic period review',
            evidence_reference='Explicit independent review',payload=dict(period=period,action=action,expected_period_revision=revision,
            attestation=dict(bank_reconciled=True,originals_complete=True,special_cases_reviewed=True)))
        preview=self.euer.preview(self.owner,body)
        if not confirm:return preview
        command=self.b.req(**body,preview_hash=preview['preview_hash'],confirmation=True)
        return self.euer.confirm(self.owner,command),command

    def test_old_manual_close_is_exact_but_new_close_requires_current_configured_bank_proof(self):
        old,command=self.period('2026-10','close',0)
        original=canonical(old);self.assertNotIn('bank_reconciliation',old['control'])
        self.b.binding=self.b.bank.save_account(self.owner,self.b.account_body())
        self.assertEqual(canonical(self.euer.confirm(self.owner,command)),original)
        with self.assertRaises(Problem) as missing:self.period('2026-11','close',0)
        self.assertEqual(missing.exception.status,409)
        statement,_=self.b.save_statement([]);report,_=self.b.report([statement])
        closed,_=self.period('2026-11','close',0)
        self.assertEqual(closed['control']['bank_reconciliation']['reconciliations'][0]['id'],report['record']['id'])
        self.period('2026-11','reopen',1)
        self.b.binding=self.b.bank.save_account(self.owner,self.b.account_body(revision=1,label='Reviewed account label',reason='Documented label correction'))
        with self.assertRaises(Problem) as stale:self.period('2026-11','close',2)
        self.assertEqual(stale.exception.status,409)
        self.assertTrue(validate_euer(self.office))
        self.assertEqual(canonical(self.euer.confirm(self.owner,command)),original)
        # Historical close validation reads frozen bank reports without adding
        # bank.read or any personnel permission to ordinary EÜR readers.
        reader=self.f.reader(self.f.tech)
        self.assertEqual(self.euer.report(reader,2026)['totals'],self.euer.report(self.owner,2026)['totals'])

    def test_horizon11_exact_scope_rejects_bad_counts_hashes_and_retains_historical10(self):
        self.b.binding=self.b.bank.save_account(self.owner,self.b.account_body())
        statement,_=self.b.save_statement([]);self.b.report([statement])
        complete=business_schema.financial_accounting_horizon(self.office)
        self.assertEqual(complete['schema_version'],12)
        business_schema._validate_financial_accounting_horizon(complete,13)
        value={key:item for key,item in complete.items() if key not in ('travel_cash','opening_balances')};value['schema_version']=10
        original=canonical(value);business_schema._validate_financial_accounting_horizon(value,11)
        self.assertEqual(canonical(value),original)
        previous={key:item for key,item in value.items() if key!='bank_reconciliation'};previous['schema_version']=9
        encoded=canonical(previous);business_schema._validate_financial_accounting_horizon(previous,10)
        self.assertEqual(canonical(previous),encoded)
        for case in ('missing','extra','boolean_count','negative_count','boolean_schema','invalid_hash'):
            bad=json.loads(original);bank=bad['bank_reconciliation']
            if case=='missing':bank['table_counts'].pop('business_bank_statements')
            elif case=='extra':bank['table_counts']['invented_table']=0
            elif case=='boolean_count':bank['table_counts']['business_bank_statements']=True
            elif case=='negative_count':bank['table_counts']['business_bank_statements']=-1
            elif case=='boolean_schema':bank['schema_version']=True
            else:bank['sha256']='F'*64
            with self.subTest(case=case),self.assertRaises(ValueError):business_schema._validate_financial_accounting_horizon(bad,11)
        with self.assertRaises(ValueError):business_schema._validate_financial_accounting_horizon(previous,11)
        with self.assertRaises(ValueError):business_schema._validate_financial_accounting_horizon(value,10)


if __name__=='__main__':unittest.main()
