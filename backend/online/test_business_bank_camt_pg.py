"""Actual MFA, restricted PostgreSQL writers, bank match and complete restore."""
import base64
import calendar
from concurrent.futures import ThreadPoolExecutor
import time
import unittest
import uuid
from xml.etree import ElementTree as XML

import business_schema
from business_bank_camt import CamtBankReconciliation
from business_bank_reconciliation import TABLES, restore_horizon, validate_integrity
from business_foundation import BusinessFoundation
from core import Problem
from online import test_business_bank_reconciliation_pg as base, release
from online.store import PostgresOffice
from online.auth import totp
from online.test_postgres_accounting_components_integration import disposable_restore, evidence_for, approve
from test_bank_camt_2026_v1 import statement, NAMESPACE

fixture, req = base.fixture, base.req


def bank_xml(day):
    root = XML.fromstring(statement())
    ns = {'b': NAMESPACE}
    main = root.find('b:BkToCstmrStmt/b:Stmt', ns)
    end = calendar.monthrange(int(day[:4]), int(day[5:7]))[1]
    first, last = day[:7]+'-01', day[:7]+'-'+str(end)
    def set_text(node, path, value): node.find('/'.join('b:'+p for p in path.split('/')), ns).text = value
    set_text(main, 'Id', 'synthetic-camt-'+uuid.uuid4().hex[:16])
    set_text(main, 'FrToDt/FrDtTm', first+'T00:00:00+01:00')
    set_text(main, 'FrToDt/ToDtTm', last+'T23:59:59+01:00')
    balances = main.findall('b:Bal', ns)
    for balance, value, when in ((balances[0], '0.00', first), (balances[1], '119.00', last)):
        set_text(balance, 'Amt', value); set_text(balance, 'Dt/Dt', when)
    entries = main.findall('b:Ntry', ns)
    main.remove(entries[1])
    set_text(entries[0], 'Amt', '119.00')
    set_text(entries[0], 'BookgDt/Dt', day); set_text(entries[0], 'ValDt/Dt', day)
    return XML.tostring(root, encoding='utf-8', xml_declaration=True)


@unittest.skipUnless(fixture.DSN, 'Own disposable loopback PostgreSQL required')
class CamtBankPostgres(unittest.TestCase):
    setUp = base.BankReconciliationPostgres.setUp
    reopen = base.BankReconciliationPostgres.reopen
    call = base.BankReconciliationPostgres.call
    profile = base.BankReconciliationPostgres.profile
    post = base.BankReconciliationPostgres.post
    project = base.BankReconciliationPostgres.project
    issuer = base.BankReconciliationPostgres.issuer
    invoice = base.BankReconciliationPostgres.invoice
    payment = base.BankReconciliationPostgres.payment
    source = base.BankReconciliationPostgres.source
    document = base.BankReconciliationPostgres.document
    cash = base.BankReconciliationPostgres.cash
    setup_bank = base.BankReconciliationPostgres.setup_bank
    match_command = base.BankReconciliationPostgres.match_command
    report = base.BankReconciliationPostgres.report

    def login(self, email, password):
        pending=self.call('POST','/login',dict(email=email,password=password),token=None).json
        self.assertTrue(pending['mfa_required'])
        secrets=getattr(self,'synthetic_mfa_secrets',{})
        secret=pending.get('enrollment',{}).get('secret') or secrets.get(email)
        self.assertIsNotNone(secret,'The unchanged synthetic MFA enrollment must be retained for restore')
        secrets[email]=secret;self.synthetic_mfa_secrets=secrets
        steps=getattr(self,'synthetic_mfa_steps',{})
        step=max(int(time.time()//30),steps.get(email,-1)+1)
        steps[email]=step;self.synthetic_mfa_steps=steps
        return self.call('POST','/login/verify',dict(challenge=pending['challenge'],code=totp(secret,step)),token=None).json['token']

    def command(self, account, binding, raw):
        request = dict(account_id=account['id'], account_revision=1,
            bank_revision=binding['revision'], filename='synthetic-bank.xml',
            content_base64=base64.b64encode(raw).decode())
        inspection = self.call('POST', '/business/bank/camt/inspect', request).json
        self.assertIs(inspection['financial_changes'], False)
        body = dict(inspection['suggested_body'], content_base64=request['content_base64'], complete_statement_confirmed=True)
        preview = self.call('POST', '/business/bank/camt/preview', body).json
        self.assertTrue(preview['can_import'], preview['errors'])
        return req(**body, preview_hash=preview['preview_hash'], confirmation=True)

    def test_actual_mfa_http_keeps_xml_original_and_matches_existing_cash_without_new_payment(self):
        account, cash, binding = self.setup_bank(); raw = bank_xml(self.today)
        self.assertIn('bank_camt_v1', self.call('GET', '/business/capabilities').json['features'])
        before = self.office.db.execute('SELECT COUNT(*) FROM business_euer_entries').fetchone()[0]
        command = self.command(account, binding, raw)
        statement = self.call('POST', '/business/bank/camt/statements', command).json
        self.assertEqual(self.call('POST', '/business/bank/camt/statements', command).json, statement)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_euer_entries').fetchone()[0], before)
        path = '/business/bank/statements/'+statement['statement']['id']+'/original'
        response = self.call('GET', path)
        self.assertEqual(response.data, raw); self.assertEqual(response.mimetype, 'application/xml')
        transaction = statement['lines'][0]['transaction_id']
        self.call('POST', '/business/bank/transactions/'+transaction+'/matches', self.match_command(transaction, '119.00'))
        report, _ = self.report(account, statement)
        self.assertTrue(report['record']['payload']['complete'])
        self.assertEqual(report['record']['payload']['bank_movement_net'], '119.00')
        self.assertEqual(report['record']['payload']['cash_movement_net'], '119.00')
        self.assertTrue(validate_integrity(self.office)); self.assertTrue(business_schema.validate_integrity(self.office))
        self.call('POST', '/business/bank/camt/preview?ignored=1', command, status=400)
        device = self.call('POST', '/business/offline/access', {}, status=201).json['token']
        self.call('POST', '/business/bank/camt/statements', command, token=device, status=403)

    def test_real_parallel_imports_and_fresh_rights_preserve_original_receipts(self):
        account, _, binding = self.setup_bank(); raw = bank_xml(self.today)
        command = self.command(account, binding, raw)
        def run(_):
            office = PostgresOffice(self.runtime)
            try: return CamtBankReconciliation(office).import_statement(self.actor, command)
            finally: office.db.close()
        with ThreadPoolExecutor(2) as pool: values = list(pool.map(run, range(2)))
        self.assertEqual(values[0], values[1])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_bank_statements').fetchone()[0], 1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_bank_transactions').fetchone()[0], 1)
        tech = self.call('POST', '/users', dict(email='camt-reader@example.test', password='Synthetic-camt-password-123', role='technician'), status=201).json
        token = self.login('camt-reader@example.test', 'Synthetic-camt-password-123')
        for permission in ('bank.read','bank.prepare','accounting.read','accounting.prepare','finance.read','finance.write'):
            BusinessFoundation(self.office).save_grant(self.actor, req(user_id=tech['id'],permission=permission,scope='*',effect='allow',revision=0))
        body = {k:v for k,v in command.items() if k not in ('request_id','preview_hash','confirmation')}
        proof = self.call('POST', '/business/bank/camt/preview', body, token=token).json
        delegated = req(**body,preview_hash=proof['preview_hash'],confirmation=True)
        saved = self.call('POST', '/business/bank/camt/statements', delegated, token=token).json
        self.assertEqual(saved, values[0])
        BusinessFoundation(self.office).save_grant(self.actor, req(user_id=tech['id'],permission='bank.prepare',scope='*',effect='deny',revision=1))
        self.call('POST', '/business/bank/camt/statements', delegated, token=token, status=403)
        self.assertTrue(validate_integrity(self.office))

    def test_full_dump_restore_preserves_xml_projection_matches_and_old_nonce(self):
        account, _, binding = self.setup_bank(); raw = bank_xml(self.today)
        command = self.command(account, binding, raw)
        saved = self.call('POST', '/business/bank/camt/statements', command).json
        transaction = saved['lines'][0]['transaction_id']
        self.call('POST', '/business/bank/transactions/'+transaction+'/matches', self.match_command(transaction,'119.00'))
        report, report_command = self.report(account, saved)
        before = restore_horizon(self.office)
        fingerprints = release.snapshot_fingerprint(fixture.DSN)
        old_token = self.token; self.office.db.close()
        with disposable_restore(self.runtime) as (target, runtime, restored_report):
            restored = PostgresOffice(runtime)
            try:
                self.assertEqual(restore_horizon(restored), before)
                api = CamtBankReconciliation(restored)
                self.assertEqual(api.original(self.actor, saved['statement']['id']), (raw,'application/xml; charset=utf-8'))
                with self.assertRaises(Problem) as error: api.import_statement(self.actor, command)
                self.assertEqual(error.exception.status,409)
                evidence = evidence_for(restored, restored_report)
                restored.db.close()
                operator = PostgresOffice(target)
                try: approve(operator, evidence)
                finally: operator.db.close()
                restored = PostgresOffice(runtime); api = CamtBankReconciliation(restored)
                self.assertEqual(api.import_statement(self.actor,command),saved)
                self.assertEqual(api.save_reconciliation(self.actor,report_command),report)
                self.assertTrue(validate_integrity(restored)); self.assertTrue(business_schema.validate_integrity(restored))
                after = release.snapshot_fingerprint(target)
                for table in TABLES: self.assertEqual(after[table],fingerprints[table])
                from online.web import create_app
                self.office = restored
                self.app = create_app(office=restored,key=self.key,host='office.example.test',storage_config={})
                self.client = self.app.test_client()
                self.call('POST','/business/bank/camt/statements',command,token=old_token,status=401)
                self.token = self.login('order-owner@example.test','Synthetic-owner-password-123')
                self.assertEqual(self.call('POST','/business/bank/camt/statements',command).json,saved)
                self.assertEqual(self.call('GET','/business/bank/statements/'+saved['statement']['id']+'/original').data,raw)
            finally: restored.db.close()


if __name__ == '__main__': unittest.main()
