"""Explicit LStDV standard-case identities, payment evidence and carry-ins."""
import json
import sqlite3
import unittest

import test_business_payroll as monthly
from business_payroll_accounts import PayrollAccounts,validate_integrity
from business_personnel_workflow import _sha
from core import Problem,canonical


class PayrollAccountTests(monthly.BusinessFixture,unittest.TestCase):
    def setUp(self):
        monthly.PayrollWorkflowTests.setUp(self)
        self.now=self.now.replace(month=11,day=3)
    case=monthly.PayrollWorkflowTests.case
    command=monthly.PayrollWorkflowTests.command

    def account_api(self):
        return PayrollAccounts(self.office,clock=lambda:self.now)

    def identity_details(self,data,**changes):
        return {**dict(profile_id=data['profile']['id'],profile_revision=data['profile']['revision'],
            given_name='Synthetic',family_name='Employee',date_of_birth='1990-02-01',address_line='Testweg 1',
            postal_code='12345',city='Teststadt',country_code='DE',tax_id='12345678903',
            employer_name='Synthetic Employer',employer_address='Teststraße 2, 12345 Teststadt',
            employer_tax_number='123/456/78901',employment_from='2026-10-01',employment_to='2026-10-31',
            tax_source='flat_minijob_evidence' if data['profile']['profile']['employment_kind']=='minijob' else 'elstam_imported',
            tax_source_date='2026-01-01',valid_from='2026-01-01',valid_to='2026-12-31',
            tax_allowance_yearly_minor=0,tax_addition_yearly_minor=0,religion_code='none',standard_case_confirmed=True),**changes}

    def save_account(self,data,kind,details,**changes):
        body={**dict(request_id=monthly.rid(),employee_id=self.employee['id'],kind=kind,revision=0,
            source_file_id=data['file']['id'],confirmed=True,details=details),**changes}
        return self.account_api().save(self.owner,body),body

    def payment_details(self,run,identity,**changes):
        return {**dict(run_id=run['id'],run_revision=run['revision'],identity_id=identity['id'],identity_revision=identity['revision'],
            payments=[dict(paid_on='2026-10-31',amount_minor=run['calculation']['net_minor'],payment_reference='SYN-WAGE-001')],
            tax_free_payments_minor=0,tax_free_basis='',standard_case_confirmed=True),**changes}

    def ledger(self):
        return self.payroll.ledger(self.owner,dict(employee_id=self.employee['id'],year='2026'))['ledger']

    def test_required_fields_and_actual_payment_complete_only_the_supported_employment_period(self):
        data=self.case('regular',500000,health_additional_percent='2.90',tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0)
        run=self.payroll.finalize(self.owner,self.command(data))
        self.assertFalse(self.ledger()['statutory_wage_account_complete'])
        identity,_=self.save_account(data,'identity',self.identity_details(data))
        self.assertFalse(self.ledger()['statutory_wage_account_complete'])
        payment,body=self.save_account(data,'payment',self.payment_details(run,identity))
        self.assertEqual(self.account_api().save(self.owner,body),payment)
        ledger=self.ledger()
        self.assertEqual(ledger['expected_employment_months'],['2026-10'])
        self.assertEqual(ledger['account_missing_months'],[])
        self.assertTrue(ledger['supported_wage_account_fields_complete'])
        self.assertTrue(ledger['statutory_wage_account_complete'])
        self.assertFalse(ledger['calendar_year_complete'])
        self.assertFalse(ledger['digital_audit_export_compliant'])
        self.assertFalse(ledger['official_system_approval'])
        self.assertEqual(ledger['months'][9]['wage_account']['payment_ref']['content_hash'],payment['content_hash'])
        self.assertEqual(ledger['recorded_tax_free_payments_minor'],0)
        self.assertTrue(validate_integrity(self.office))
        for kind in ('pdf','csv','json'):
            content,_=self.payroll.export_ledger(self.owner,dict(employee_id=self.employee['id'],year='2026',snapshot_hash=ledger['snapshot_hash']),kind)
            self.assertIn(b'12345678903',content)

    def test_corrected_identity_requires_fresh_payment_reference_and_preserves_history(self):
        data=self.case();run=self.payroll.finalize(self.owner,self.command(data))
        identity,_=self.save_account(data,'identity',self.identity_details(data))
        payment,_=self.save_account(data,'payment',self.payment_details(run,identity))
        changed,_=self.save_account(data,'identity',{**identity['details'],'address_line':'Berichtigter Testweg 2'},
            id=identity['id'],revision=1,correction_reason='Dokumentierten Schreibfehler berichtigt')
        self.assertFalse(self.ledger()['statutory_wage_account_complete'])
        self.assertIn('identity_revision_outdated',self.ledger()['months'][9]['wage_account']['issues'])
        updated,_=self.save_account(data,'payment',{**payment['details'],'identity_revision':changed['revision']},
            id=payment['id'],revision=1,correction_reason='Berichtigte Identität übernommen')
        self.assertTrue(self.ledger()['statutory_wage_account_complete'])
        history=self.account_api().get(self.owner,payment['id'],True)['items']
        self.assertEqual(history,[payment,updated])
        self.assertTrue(validate_integrity(self.office))

    def test_negative_minijob_net_records_real_employee_top_up_without_fictitious_zero_payment(self):
        data=self.case(amount=2500);run=self.payroll.finalize(self.owner,self.command(data))
        self.assertEqual(run['calculation']['net_minor'],-380)
        identity,_=self.save_account(data,'identity',self.identity_details(data))
        self.save_account(data,'payment',self.payment_details(run,identity))
        ledger=self.ledger()
        self.assertTrue(ledger['statutory_wage_account_complete'])
        self.assertEqual(ledger['months'][9]['wage_account']['payments'][0]['amount_minor'],-380)

    def test_carryover_is_documented_recomputed_and_excludes_duplicate_local_month(self):
        data=self.case()
        identity,_=self.save_account(data,'identity',self.identity_details(data))
        details=dict(month='2026-10',profile_id=data['profile']['id'],profile_revision=1,
            identity_id=identity['id'],identity_revision=1,gross_minor=60300,expected_net_minor=58129,
            expected_employee_tax_minor=0,expected_employee_social_total_minor=2171,
            expected_employer_social_total_minor=16884,expected_employer_total_minor=79095,
            payments=[dict(paid_on='2026-10-31',amount_minor=58129,payment_reference='SYN-PRIOR-001')],
            tax_free_payments_minor=0,tax_free_basis='',standard_case_confirmed=True,status='active')
        carry,body=self.save_account(data,'carryover',details)
        self.assertEqual(self.account_api().save(self.owner,body),carry)
        ledger=self.ledger()
        self.assertEqual(ledger['recorded_months'],1)
        self.assertEqual(ledger['months'][9]['origin'],'external_carryover')
        self.assertIsNone(ledger['months'][9]['run_id'])
        self.assertEqual(ledger['months'][9]['carryover_id'],carry['id'])
        self.assertEqual(ledger['totals']['gross_minor'],60300)
        self.assertTrue(ledger['statutory_wage_account_complete'])
        with self.assertRaises(Problem) as blocked:
            self.payroll.finalize(self.owner,self.command(data))
        self.assertEqual(blocked.exception.status,409)
        self.assertEqual(blocked.exception.request_resolution,'not_accepted')
        self.problem(400,lambda:self.save_account(data,'carryover',{**details,'expected_net_minor':58130},
            id=carry['id'],revision=1,correction_reason='Unbelegter Betrag'))
        void,_=self.save_account(data,'carryover',{**details,'status':'void'},id=carry['id'],revision=1,
            correction_reason='Belegten Monat durch lokalen Lauf ersetzen')
        local=self.payroll.finalize(self.owner,self.command(data))
        self.assertEqual(self.ledger()['totals']['gross_minor'],60300)
        self.assertEqual(self.ledger()['months'][9]['run_id'],local['id'])
        correction=self.ledger()['correction_history'][0]
        self.assertEqual(correction['delta']['gross_minor'],-60300)
        self.assertEqual(correction['effect'],'projection_only')
        self.problem(409,lambda:self.save_account(data,'carryover',details,id=void['id'],revision=2,
            correction_reason='Doppelter Vortrag nicht zulässig'))
        self.assertTrue(validate_integrity(self.office))

    def test_staff_permissions_source_binding_and_append_only_guards(self):
        data=self.case();identity,body=self.save_account(data,'identity',self.identity_details(data))
        self.assertEqual(self.account_api().get(self.technician,identity['id']),identity)
        self.problem(403,lambda:self.account_api().save(self.technician,body))
        uid=self.office.add_user('account-denied@example.test','Synthetic-account-password-123','accountant')
        self.problem(403,lambda:self.account_api().get(dict(id=uid,role='owner'),identity['id']))
        other=self.planning.save_employee(self.owner,dict(request_id=monthly.rid(),user_id=uid,name='Other payroll employee'))
        self.problem(404,lambda:self.account_api().save(self.owner,{**body,'request_id':monthly.rid(),'employee_id':other['id']}))
        row=dict(self.office.db.execute('SELECT * FROM business_payroll_account_events WHERE id=?',(identity['id'],)).fetchone())
        with self.assertRaises(sqlite3.IntegrityError):
            self.office.db.execute('DELETE FROM business_payroll_account_events WHERE id=?',(identity['id'],))
        row['id']=monthly.rid()
        with self.assertRaises(sqlite3.IntegrityError):
            self.office.db.execute('INSERT OR REPLACE INTO business_payroll_account_events('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values()))
        self.office.db.execute('UPDATE users SET active=0 WHERE id=?',(self.owner_id,))
        self.problem(401,lambda:self.account_api().save(self.owner,body))

    def test_same_payment_cannot_be_reused_for_two_months_or_hidden_with_unicode(self):
        data=self.case()
        identity,_=self.save_account(data,'identity',self.identity_details(data,employment_from='2026-09-01'))
        prior=dict(month='2026-09',profile_id=data['profile']['id'],profile_revision=1,
            identity_id=identity['id'],identity_revision=1,gross_minor=60300,expected_net_minor=58129,
            expected_employee_tax_minor=0,expected_employee_social_total_minor=2171,
            expected_employer_social_total_minor=16884,expected_employer_total_minor=79095,
            payments=[dict(paid_on='2026-10-31',amount_minor=58129,payment_reference='SYN-001')],
            tax_free_payments_minor=0,tax_free_basis='',standard_case_confirmed=True,status='active')
        self.save_account(data,'carryover',prior)
        run=self.payroll.finalize(self.owner,self.command(data))
        for reference in ('SYN-001','syn-001','ＳＹＮ-001'):
            with self.subTest(reference=reference):
                payment=self.payment_details(run,identity,payments=[dict(paid_on='2026-10-31',amount_minor=58129,payment_reference=reference)])
                self.problem(409,lambda:self.save_account(data,'payment',payment))
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM business_payroll_account_events WHERE kind='payment'").fetchone()[0],0)
        self.assertTrue(validate_integrity(self.office))

    def test_rehashed_payment_tamper_still_fails_referenced_run_and_amount_validation(self):
        data=self.case();run=self.payroll.finalize(self.owner,self.command(data))
        identity,_=self.save_account(data,'identity',self.identity_details(data))
        payment,_=self.save_account(data,'payment',self.payment_details(run,identity))
        row=dict(self.office.db.execute('SELECT * FROM business_payroll_account_events WHERE id=?',(payment['id'],)).fetchone())
        payload=json.loads(row['payload_json']);payload['details']['payments'][0]['amount_minor']+=1
        envelope={key:row[key] for key in ('id','revision','kind','employee_id','identity_key','previous_hash','created_by','created_at')}
        envelope['payload']=payload
        self.office.db.execute('DROP TRIGGER business_payroll_account_events_update_guard')
        self.office.db.execute('UPDATE business_payroll_account_events SET payload_json=?,content_hash=? WHERE id=?',
            (canonical(payload),_sha(envelope),payment['id']))
        with self.assertRaisesRegex(ValueError,'Invalid payroll account archive'):
            validate_integrity(self.office)

    def test_missing_or_contradictory_mandatory_fields_and_future_actual_payment_are_rejected(self):
        data=self.case('regular',500000,health_additional_percent='2.90',tax_allowance_monthly_minor=20000,tax_addition_monthly_minor=0)
        details=self.identity_details(data)
        self.problem(400,lambda:self.save_account(data,'identity',details))  # Annual zero contradicts monthly 200 EUR.
        details['tax_allowance_yearly_minor']=240000
        for changes in ({'tax_id':'123'},{'given_name':''},{'date_of_birth':'1991-02-01'},
                {'tax_source_date':'2026-11-04'},{'valid_from':'2025-12-01'},
                {'standard_case_confirmed':False}):
            with self.subTest(changes=changes):
                self.problem(400,lambda:self.save_account(data,'identity',{**details,**changes}))
        identity,_=self.save_account(data,'identity',details)
        run=self.payroll.finalize(self.owner,self.command(data))
        payment=self.payment_details(run,identity,payments=[dict(paid_on='2026-11-04',amount_minor=run['calculation']['net_minor'],payment_reference='SYN-FUTURE')])
        self.problem(400,lambda:self.save_account(data,'payment',payment))
        self.assertFalse(self.ledger()['statutory_wage_account_complete'])


if __name__=='__main__':
    unittest.main()
