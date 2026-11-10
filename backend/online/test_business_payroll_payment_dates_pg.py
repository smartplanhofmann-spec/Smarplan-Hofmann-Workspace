"""Actual bound MFA/PostgreSQL later transfers, private proofs and dump restore."""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import threading
import time
import unittest

import business_schema
from business_payroll import Payroll
from business_payroll_accounts import PayrollAccounts
from business_payroll_cash import PayrollCash
from business_accounting_euer import EuerAccounting
from business_payroll_facts import reference
from online.store import PostgresOffice
from online.auth import totp
from online import test_business_payroll_positive_corrections_pg as prior
from online.test_postgres_accounting_components_integration import disposable_restore, evidence_for, approve


@unittest.skipUnless(prior.fixture.DSN, 'Guarded disposable loopback PostgreSQL required')
class ActualPaymentDatesPostgres(unittest.TestCase):
    setUpClass = classmethod(prior.PositiveCorrectionPostgres.setUpClass.__func__)
    windows_calculate = prior.PositiveCorrectionPostgres.windows_calculate
    setUp = prior.PositiveCorrectionPostgres.setUp
    reopen = prior.PositiveCorrectionPostgres.reopen
    call = prior.PositiveCorrectionPostgres.call
    sources = prior.PositiveCorrectionPostgres.sources
    profile = prior.PositiveCorrectionPostgres.profile
    post = prior.PositiveCorrectionPostgres.post
    cash_body = prior.PositiveCorrectionPostgres.cash_body
    cash_payload = prior.PositiveCorrectionPostgres.cash_payload
    private_file = prior.PositiveCorrectionPostgres.private_file
    forecast = prior.PositiveCorrectionPostgres.forecast
    save_case = prior.PositiveCorrectionPostgres.save_case
    prepare_run = prior.PositiveCorrectionPostgres.prepare_run
    review = prior.PositiveCorrectionPostgres.review
    workflow = prior.PositiveCorrectionPostgres.workflow
    correction = prior.PositiveCorrectionPostgres.correction
    import_net = prior.PositiveCorrectionPostgres.import_net

    def login(self, email, password):
        pending = self.call('POST', '/login', {'email': email, 'password': password}, token=None).json
        self.assertTrue(pending['mfa_required'])
        secrets = getattr(self, '_enrolled_secrets', {})
        if 'enrollment' in pending:
            secrets[email] = pending['enrollment']['secret']
        self._enrolled_secrets = secrets
        self.assertIn(email, secrets, 'Renewed MFA must use the actually enrolled original secret')
        steps = getattr(self, '_accepted_mfa_steps', {})
        deadline = time.monotonic()+31
        while int(time.time()//30) <= steps.get(email, -1):
            self.assertLess(time.monotonic(), deadline, 'Real MFA clock did not advance')
            time.sleep(.1)
        step = int(time.time()//30)
        self._accepted_mfa_steps = dict(steps, **{email: step})
        return self.call('POST', '/login/verify', {'challenge': pending['challenge'],
            'code': totp(secrets[email], step)}, token=None).json['token']

    def pay(self, data, run, old=None, *, day='2026-11-02', submit=True):
        if old is None:
            return prior.PositiveCorrectionPostgres.pay(self, data, run)
        details = deepcopy(old['details'])
        details.update(run_id=run['id'], run_revision=run['revision'],
                       payment_source_schema_version=3, prior_payment_ref=reference(old))
        index = len(details['payments'])
        delta = run['settlement_transition']['additional_net_minor']
        details['payments'].append(dict(paid_on=day, amount_minor=delta,
            payment_reference='SYN-PG-ACTUAL-LATER-'+day+'-'+str(run['revision'])))
        details['settlement_allocations'].append(dict(payment_index=index, running_minor=0,
            one_off_allocations=[dict(event_key=run['settlement_transition']['event_key'], net_minor=delta)]))
        command = prior.req(employee_id=data['employee']['id'], kind='payment', revision=0,
                            source_file_id=data['file']['id'], confirmed=True, details=details)
        if not submit:
            return None, command
        response = self.client.post('/api/v1/business/payroll/account-records', json=command,
            base_url='https://office.example.test', headers={'Authorization': 'Bearer '+self.token})
        self.assertEqual(response.status_code, 200, response.json if response.is_json else 'non-JSON failure')
        return response.json, command

    def test_actual_later_transfer_private_mfa_euer_and_originals_survive_dump_restore(self):
        data = self.workflow(money=True, windows_original=True)
        old, old_payment = data['run'], data['payment']
        old_pdf = self.call('GET', '/business/payroll/runs/'+old['id']+'/pdf').data
        _, _, command = self.correction(data)
        run = self.call('POST', '/business/payroll/runs', command).json
        paid, pay_command = self.pay(data, run, old_payment)
        plan = paid['sources']['single_payment_plan']
        self.assertEqual(plan['schema_version'], 3)
        self.assertEqual(plan['bonus_receipt_date'], '2026-10-31')
        self.assertEqual(plan['payments'][-1]['paid_on'], '2026-11-02')
        self.assertEqual(paid['details']['payments'][:2], old_payment['details']['payments'])
        batch, cash_command = self.import_net(paid, [2])
        movement = batch['public_source']['cash_movements'][0]
        self.assertEqual(movement['date'], '2026-11-02')
        self.assertEqual(Decimal(movement['amount']), Decimal(run['settlement_transition']['additional_net_minor'])/100)
        self.post('payroll_cash', self.cash_payload(batch))
        report = self.call('GET', '/business/accounting/euer/report?year=2026').json
        self.assertEqual(Decimal(report['totals']['confirmed_expenses']),
            Decimal(run['calculation']['net_minor']-run['calculation']['net_deductions_minor'])/100)
        self.call('GET', '/business/payroll/account-records/'+paid['id'], token=data['tech'], status=403)
        self.call('POST', '/business/payroll/account-records', pay_command, token=data['tech'], status=403)
        grant = self.call('POST', '/business/offline/access/v2', {}, status=201).json
        origin = grant['binding']['instance_id']+':'+grant['binding']['account_id']
        self.call('GET', '/business/payroll/account-records/'+paid['id'], token=grant['token'], offline_origin=origin, status=403)
        self.assertEqual(self.call('POST', '/business/payroll/account-records', pay_command).json, paid)
        self.assertEqual(self.call('GET', '/business/payroll/account-records/'+old_payment['id']).json, old_payment)
        self.assertTrue(business_schema.validate_integrity(self.office))
        self.office.db.close()
        with disposable_restore(self.runtime) as (target, runtime, restore_report):
            operator = PostgresOffice(target)
            try:
                approve(operator, evidence_for(operator, restore_report))
            finally:
                operator.db.close()
            restored = PostgresOffice(runtime)
            try:
                self.assertEqual(Payroll(restored).finalize(self.owner, command), run)
                self.assertEqual(PayrollAccounts(restored).save(self.owner, pay_command), paid)
                self.assertEqual(PayrollCash(restored).confirm(self.owner, cash_command), batch)
                self.assertEqual(Payroll(restored).export(self.owner, old['id'], 'pdf', revision='1')[0], old_pdf)
                self.assertEqual(EuerAccounting(restored).report(self.owner, 2026)['totals'], report['totals'])
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:
                restored.db.close()

    def test_two_actual_payment_writers_and_fresh_role_withdrawal(self):
        data = self.workflow()
        _, _, command = self.correction(data)
        run = self.call('POST', '/business/payroll/runs', command).json
        _, payment_command = self.pay(data, run, data['payment'], submit=False)
        barrier = threading.Barrier(2)
        def apply(_):
            office = PostgresOffice(self.runtime)
            try:
                barrier.wait(timeout=10)
                return PayrollAccounts(office).save(self.owner, payment_command)
            finally:
                office.db.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(apply, range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(self.call('POST', '/business/payroll/account-records', payment_command).json, results[0])
        with self.office.db:
            self.office.db.execute("UPDATE users SET role='technician' WHERE id=?", (self.owner['id'],))
        self.call('POST', '/business/payroll/account-records', payment_command, status=403)
        with self.office.db:
            self.office.db.execute("UPDATE users SET role='owner' WHERE id=?", (self.owner['id'],))
        self.token = self.login('order-owner@example.test', 'Synthetic-owner-password-123')
        self.assertEqual(self.call('POST', '/business/payroll/account-records', payment_command).json, results[0])
        self.assertTrue(business_schema.validate_integrity(self.office))


if __name__ == '__main__':
    unittest.main()
