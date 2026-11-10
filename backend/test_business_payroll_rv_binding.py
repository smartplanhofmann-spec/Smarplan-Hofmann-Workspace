"""Actual RV originals bind profiles and payroll without rewriting old money."""
from copy import deepcopy
import json

from core import Problem,canonical
from business_payroll_facts import reference
from test_business_payroll_rv_lifecycle import RvLifecycleFixture,rid,settled,request


class RvPayrollBinding(RvLifecycleFixture):
    def lifecycle(self, *, pending=False):
        body=self.body()
        (request if pending else settled)(body['details']['assessment'])
        return self.save(body)[0]

    def profile_command(self,record, *, effective='2026-08-01', exempt=False, previous=None):
        f=self.f
        result=dict(request_id=rid(),employee_id=f.employee['id'],revision=previous['revision'] if previous else 0,
            profile=dict(self.data['profile']['profile'],effective_from=effective,minijob_rv_exempt=exempt),
            source_file_id=self.file['id'],confirmed=True,
            rv_lifecycle_source_contract_version=1,rv_lifecycle_ref=reference(record))
        if previous:result.update(id=previous['id'],correction_reason='Synthetic unchanged status bound to reviewed original revision')
        return result

    def bound(self,record,**options):
        profile=self.f.payroll.save_profile(self.f.owner,self.profile_command(record,**options))
        self.data['inputs'].update(profile_id=profile['id'],profile_revision=profile['revision'])
        return profile

    def denied(self,status,action):
        with self.assertRaises(Problem) as error:action()
        self.assertEqual(error.exception.status,status,error.exception.message)
        return error.exception

    def test_current_original_is_required_and_exact_profile_receipt_survives_later_review(self):
        record=self.lifecycle();command=self.profile_command(record)
        for change in [dict(rv_lifecycle_source_contract_version=True),dict(rv_lifecycle_ref=dict(reference(record),content_hash='f'*64)),
                dict(profile=dict(command['profile'],minijob_rv_exempt=True))]:
            self.denied(400 if 'rv_lifecycle_source_contract_version' in change else 409,
                lambda change=change:self.f.payroll.save_profile(self.f.owner,dict(command,**change)))
        unbound=deepcopy(command)
        for key in ('rv_lifecycle_source_contract_version','rv_lifecycle_ref'):unbound.pop(key)
        self.denied(409,lambda:self.f.payroll.save_profile(self.f.owner,unbound))
        saved=self.f.payroll.save_profile(self.f.owner,command)
        body=deepcopy(self.body());settled(body['details']['assessment']);body['details']['assessment']['review_note']='Synthetic later unchanged original review'
        body['details']['prior_assessment_refs']=[reference(record)]
        current,_=self.save(body,record)
        self.assertEqual(self.f.payroll.save_profile(self.f.owner,command),saved)
        self.denied(409,lambda:self.f.payroll.save_profile(self.f.owner,self.profile_command(record,effective='2026-09-01')))
        self.assertEqual(self.f.payroll.save_profile(self.f.owner,self.profile_command(current,effective='2026-09-01'))['rv_lifecycle_ref'],reference(current))

    def test_actual_revoked_rv_changes_only_new_monthly_money_and_preserves_originals(self):
        f=self.f
        old_command=f.command(self.data);old_run=f.payroll.finalize(f.owner,old_command)
        old_pdf=f.payroll.export(f.owner,old_run['id'],'pdf')[0]
        self.assertEqual(old_run['calculation']['net_minor'],60300)
        record=self.lifecycle()
        self.denied(409,lambda:f.payroll.preview(f.owner,self.data['inputs']))
        profile=self.bound(record)
        preview=f.payroll.preview(f.owner,self.data['inputs'])
        self.assertEqual(preview['calculation']['net_minor'],58129)
        self.assertEqual(preview['source']['profile']['rv_lifecycle_ref'],reference(record))
        command=f.command(self.data,id=old_run['id'],revision=1,correction_reason='Synthetic actual documented RV revocation')
        run=f.payroll.finalize(f.owner,command)
        self.assertEqual(run['calculation']['employee_social_total_minor'],2171)
        self.assertEqual(run['delta']['net_minor'],-2171)
        self.assertEqual(f.payroll.finalize(f.owner,old_command),old_run)
        self.assertEqual(f.payroll.finalize(f.owner,command),run)
        self.assertEqual(f.payroll.export(f.owner,old_run['id'],'pdf','1')[0],old_pdf)
        self.assertEqual(json.loads(f.payroll.export(f.owner,old_run['id'],'json','1')[0]),old_run)
        self.assertEqual(f.payroll.get(f.owner,'profile',self.data['profile']['id']),self.data['profile'])
        from business_payroll_statements import project
        own=project(run);self.assertEqual(own['calculation']['net_minor'],58129)
        self.assertNotIn('rv_lifecycle',canonical(own));self.assertNotIn('authority_evidence_ref',canonical(own))
        from business_schema import validate_integrity
        self.assertTrue(validate_integrity(f.office))

    def test_pending_procedure_cannot_be_silently_used_for_payroll(self):
        record=self.lifecycle(pending=True)
        self.denied(409,lambda:self.bound(record))
        before=self.bound(record,effective='2026-05-01',exempt=True)
        self.assertEqual(before['rv_lifecycle_ref'],reference(record))
        # The profile was valid in May, but the actual payroll month is October.
        self.denied(409,lambda:self.f.payroll.preview(self.f.owner,self.data['inputs']))
        self.assertEqual(self.f.office.db.execute("SELECT count(*) AS n FROM business_payroll_events WHERE kind='run'").fetchone()['n'],0)

    def test_rehashed_profile_status_cannot_replace_the_original_rv_evidence(self):
        from business_personnel_workflow import _sha
        from business_payroll import COLUMNS
        f=self.f;record=self.lifecycle();profile=self.bound(record)
        row=dict(f.office.db.execute('SELECT * FROM business_payroll_events WHERE id=?',(profile['id'],)).fetchone())
        payload=json.loads(row['payload_json']);payload['profile']['minijob_rv_exempt']=True
        envelope={k:row[k] for k in COLUMNS.split(',') if k not in ('payload_json','content_hash')};envelope['payload']=payload
        f.office.db.execute('DROP TRIGGER business_payroll_events_update_guard')
        f.office.db.execute('UPDATE business_payroll_events SET payload_json=?,content_hash=? WHERE id=?',
            (canonical(payload),_sha(envelope),profile['id']))
        self.denied(500,lambda:f.payroll.get(f.owner,'profile',profile['id']))

    def test_fresh_review_requires_profile_rebinding_but_old_run_remains_readable(self):
        f=self.f;record=self.lifecycle();profile=self.bound(record)
        command=f.command(self.data);run=f.payroll.finalize(f.owner,command)
        pdf=f.payroll.export(f.owner,run['id'],'pdf')[0]
        body=self.body();settled(body['details']['assessment']);body['details']['prior_assessment_refs']=[reference(record)]
        body['details']['assessment']['review_note']='Synthetic follow-up complete review without altered original application'
        current,_=self.save(body,record)
        self.denied(409,lambda:f.payroll.preview(f.owner,self.data['inputs']))
        self.assertEqual(f.payroll.finalize(f.owner,command),run)
        self.assertEqual(f.payroll.export(f.owner,run['id'],'pdf')[0],pdf)
        revised=self.bound(current,previous=profile)
        self.assertEqual(revised['revision'],2)
        self.assertEqual(f.payroll.preview(f.owner,self.data['inputs'])['calculation'],run['calculation'])
        self.assertEqual(f.payroll.get(f.owner,'run',run['id']),run)
        # Once bound, the established-exemption original cannot be edited away.
        self.denied(409,lambda:f.payroll.save_profile(f.owner,self.profile_command(current,effective='2026-01-01',exempt=True,previous=self.data['profile'])))

    def test_every_used_period_profile_is_checked_and_private_rights_are_fresh(self):
        from business_payroll_rv_lifecycle import guard_prepared_payroll,used_profiles
        f=self.f;record=self.lifecycle();profile=self.bound(record)
        result=f.payroll.preview(f.owner,self.data['inputs'])
        second=deepcopy(self.data['profile']);second['profile']['effective_from']='2026-10-15'
        result['source']['period_case']=dict(sources=dict(profiles=[profile,second]))
        result['calculation']['period_details']=dict(tax_periods=[dict(profile_ref=reference(profile))],
            social_periods=[dict(profile_ref=reference(second))])
        self.assertEqual(len(used_profiles(result['source'],result['calculation'])),2)
        self.denied(409,lambda:guard_prepared_payroll(f.office,f.owner,result,clock=lambda:f.now))
        self.denied(403,lambda:guard_prepared_payroll(f.office,f.technician,result,clock=lambda:f.now))
        from business_foundation import BusinessFoundation
        foundation=BusinessFoundation(f.office)
        foundation.save_grant(f.owner,dict(request_id=rid(),user_id=f.technician['id'],permission='personnel.read',scope='*',effect='allow',revision=0))
        self.assertEqual(f.payroll.preview(f.technician,self.data['inputs'])['source']['profile'],profile)
        foundation.save_grant(f.owner,dict(request_id=rid(),user_id=f.technician['id'],permission='personnel.read',scope='*',effect='deny',revision=1))
        self.denied(403,lambda:f.payroll.preview(f.technician,self.data['inputs']))

    def test_actual_net_remittance_euer_annual_account_and_employee_pdf_keep_rv_private(self):
        import test_business_payroll_accounts as accounts
        import test_business_payroll_calculations as calculations
        from business_payroll_accounts import PayrollAccounts
        from business_payroll_statements import PayrollStatements
        from business_personnel_workflow import _sha
        from business_schema import validate_integrity
        f=self.f;record=self.lifecycle();profile=self.bound(record)
        run=f.payroll.finalize(f.owner,f.command(self.data))
        data=dict(self.data,profile=profile);api=PayrollAccounts(f.office,clock=lambda:f.now)
        def save(kind,details):
            return api.save(f.owner,dict(request_id=rid(),employee_id=f.employee['id'],kind=kind,revision=0,
                source_file_id=self.file['id'],confirmed=True,details=details))
        identity=save('identity',accounts.PayrollAccountTests.identity_details(f,data,
            employment_from='2026-01-01',employment_to=None,valid_from='2026-08-01'))
        payment=save('payment',accounts.PayrollAccountTests.payment_details(f,run,identity))
        finance=calculations.CalculationPayrollWorkflow.finance(self)
        command=finance.command(finance.body(payment));net=finance.api.confirm(f.owner,command)
        self.assertEqual(finance.api.confirm(f.owner,command),net)
        self.assertEqual(finance.euer.report(f.owner,2026)['totals']['confirmed_expenses'],'0.00')
        finance.post('payroll_cash',finance.payload(net))
        remittance=finance.import_cash(finance.remittance(data,run,payment,
            settlement=dict(paid_on='2026-10-31',payment_reference='SYN-RV-REMITTANCE-001',amount_minor=20966,
                source_file_id=self.file['id'],employee_id=f.employee['id'],sha256=data['file']['sha256'])))
        finance.post('payroll_cash',finance.payload(remittance))
        self.assertEqual(finance.euer.report(f.owner,2026)['totals']['confirmed_expenses'],'790.95')
        self.assertNotIn('rv_lifecycle',canonical(net['public_source']))
        self.assertNotIn('authority_evidence_ref',canonical(remittance['public_source']))
        ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))['ledger']
        self.assertEqual(ledger['months'][9]['wage_account']['payment_ref'],reference(payment))
        self.assertTrue(ledger['months'][9]['wage_account']['complete'])
        self.assertFalse(ledger['calendar_year_complete'])
        self.assertEqual(ledger['totals']['net_minor'],58129)
        for format_ in ('pdf','csv','json'):
            self.assertTrue(f.payroll.export_ledger(f.owner,dict(employee_id=f.employee['id'],year='2026',snapshot_hash=ledger['snapshot_hash']),format_)[0])
        own=PayrollStatements(f.office).get(f.technician,run['id'],{})['statement']
        pdf,mime=PayrollStatements(f.office).export(f.technician,run['id'],dict(revision='1',statement_hash=own['statement_hash']))
        self.assertEqual(mime,'application/pdf');self.assertEqual(_sha(pdf),own['pdf_sha256'])
        self.assertNotIn('rv_lifecycle',canonical(own));self.assertNotIn(record['id'],canonical(own))
        self.assertNotIn(record['id'].encode(),pdf)
        self.assertTrue(validate_integrity(f.office))


if __name__=='__main__':
    import unittest
    unittest.main()
