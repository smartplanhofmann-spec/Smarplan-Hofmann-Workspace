"""Real archived wage preparation to exact calculation, correction and exports."""
import base64
import json
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core import Problem,canonical
from business_personnel_workflow import PersonnelWorkflow,_sha
from business_payroll import Payroll,validate_integrity,dispatch,COLUMNS
from business_foundation import BusinessFoundation
from test_business_planning import BusinessFixture,rid
from test_payroll_de_2026 import profile
from payroll_de_2026 import calculate,RULE_VERSION


class PayrollWorkflowTests(BusinessFixture,unittest.TestCase):
    def setUp(self):
        self.prepare()
        self.hr=PersonnelWorkflow(self.office,clock=lambda:self.now)
        self.payroll=Payroll(self.office,clock=lambda:self.now)

    def case(self,kind='minijob',amount=60300,**profile_changes):
        file=self.hr.upload(self.owner,dict(request_id=rid(),employee_id=self.employee['id'],purpose='personnel',
            owner_visible=False,filename='verified-payroll-profile.pdf',media_type='application/pdf',
            content_base64=base64.b64encode(b'%PDF-1.4\nSynthetic reviewed payroll evidence\n%%EOF').decode()))
        agreement=self.hr.save_agreement(self.owner,dict(request_id=rid(),employee_id=self.employee['id'],revision=0,
            effective_from='2026-01-01',employment_kind=kind,pay_basis='monthly',amount_minor=amount,currency='EUR',reference_file_id=file['id']))
        saved=self.payroll.save_profile(self.owner,dict(request_id=rid(),employee_id=self.employee['id'],revision=0,
            profile=profile(kind,regular_annual_gross_minor=amount*12,**profile_changes),source_file_id=file['id'],confirmed=True))
        preview=self.hr.preview(self.owner,dict(employee_id=self.employee['id'],month='2026-10'))
        preparation=self.hr.close_preparation(self.owner,dict(request_id=rid(),employee_id=self.employee['id'],month='2026-10',
            revision=0,source_hash=preview['source_hash'],completeness_confirmed=True))
        inputs=dict(employee_id=self.employee['id'],profile_id=saved['id'],profile_revision=saved['revision'],
            preparation_id=preparation['id'],preparation_revision=preparation['revision'],gross_minor=amount,full_month_confirmed=True)
        return dict(file=file,agreement=agreement,profile=saved,preparation=preparation,inputs=inputs)

    def command(self,data,**changes):
        preview=self.payroll.preview(self.owner,data['inputs'])
        return {**data['inputs'],**dict(request_id=rid(),preview_hash=preview['preview_hash'],accepted_scope=preview['calculation']['scope'],confirmed=True,revision=0),**changes}

    def test_minijob_calculation_from_actual_salary_document_exports_and_replays(self):
        data=self.case()
        command=self.command(data)
        result=self.payroll.finalize(self.owner,command)
        self.assertEqual(self.payroll.finalize(self.owner,command),result)
        self.assertEqual(result['calculation']['net_minor'],58129)
        self.assertEqual(result['calculation']['employer_total_excluding_accident_insurance_minor'],79095)
        self.assertTrue(result['calculation']['payroll_calculation_complete'])
        self.assertEqual(result['transmission_status'],'not_transmitted')
        self.assertEqual(result['source']['preparation'],data['preparation'])
        pdf,mime=self.payroll.export(self.owner,result['id'],'pdf')
        self.assertEqual(mime,'application/pdf')
        self.assertTrue(pdf.startswith(b'%PDF-'))
        self.assertEqual(_sha(pdf),result['pdf_sha256'])
        source,_=self.payroll.export(self.owner,result['id'],'json')
        self.assertEqual(json.loads(source),result)
        self.assertTrue(validate_integrity(self.office))

    def test_regular_scope_only_records_verified_social_contributions(self):
        data=self.case('regular',350000)
        command=self.command(data)
        self.assertEqual(command['accepted_scope'],'social_contributions_only')
        result=self.payroll.finalize(self.owner,command)
        self.assertFalse(result['calculation']['payroll_calculation_complete'])
        self.assertIsNone(result['calculation']['net_minor'])
        self.assertIsNone(result['calculation']['individual_wage_tax_minor'])
        self.assertEqual(result['calculation']['employee_social_total_minor'],75758)
        self.assertTrue(validate_integrity(self.office))

    def test_regular_pap_run_and_allowance_correction_retain_historical_results_and_pdf(self):
        data=self.case('regular',500000,health_additional_percent='2.90',
            tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0)
        command=self.command(data)
        self.assertEqual(command['accepted_scope'],'regular_standard_monthly')
        result=self.payroll.finalize(self.owner,command)
        self.assertEqual(result['calculation']['individual_wage_tax_minor'],78241)
        self.assertEqual(result['calculation']['net_minor'],313009)
        original_pdf=self.payroll.export(self.owner,result['id'],'pdf')[0]
        revised=self.payroll.save_profile(self.owner,dict(request_id=rid(),employee_id=self.employee['id'],
            id=data['profile']['id'],revision=1,profile={**data['profile']['profile'],'tax_allowance_monthly_minor':20000},
            source_file_id=data['file']['id'],confirmed=True,correction_reason='Belegten monatlichen Freibetrag berichtigt'))
        self.assertEqual(self.payroll.finalize(self.owner,command),result)
        data['inputs']['profile_revision']=revised['revision']
        correction=self.payroll.finalize(self.owner,self.command(data,id=result['id'],revision=1,
            correction_reason='Freibetrag gemäß Nachweis rückgerechnet'))
        self.assertGreater(correction['calculation']['net_minor'],result['calculation']['net_minor'])
        self.assertEqual(correction['delta']['net_minor'],-correction['delta']['employee_tax_minor'])
        self.assertEqual(correction['delta']['employee_social_total_minor'],0)
        self.assertEqual(self.payroll.export(self.owner,result['id'],'pdf','1')[0],original_pdf)
        self.assertEqual(json.loads(self.payroll.export(self.owner,result['id'],'json','1')[0]),result)
        self.assertTrue(validate_integrity(self.office))

    def test_legacy_social_only_run_remains_exact_when_tax_profile_is_completed(self):
        data=self.case('regular',500000,health_additional_percent='2.90')
        def old_engine(*args,**kwargs):
            return calculate(*args,**{**kwargs,'rule_version':RULE_VERSION})
        with patch('business_payroll.calculate',side_effect=old_engine):
            command=self.command(data)
            original=self.payroll.finalize(self.owner,command)
        original_pdf=self.payroll.export(self.owner,original['id'],'pdf')[0]
        revised=self.payroll.save_profile(self.owner,dict(request_id=rid(),employee_id=self.employee['id'],
            id=data['profile']['id'],revision=1,profile={**data['profile']['profile'],
                'tax_allowance_monthly_minor':0,'tax_addition_monthly_minor':0},
            source_file_id=data['file']['id'],confirmed=True,correction_reason='Steuermerkmale vollständig nachgewiesen'))
        data['inputs']['profile_revision']=revised['revision']
        updated=self.payroll.finalize(self.owner,self.command(data,id=original['id'],revision=1,
            correction_reason='Bisher unvollständige Steuerberechnung vervollständigt'))
        self.assertEqual(original['calculation']['scope'],'social_contributions_only')
        self.assertIsNone(original['calculation']['net_minor'])
        self.assertEqual(updated['calculation']['net_minor'],313009)
        self.assertIsNone(updated['delta']['net_minor'])  # Unknown old net must never become zero.
        self.assertIsNone(updated['delta']['employee_tax_minor'])
        self.assertEqual(self.payroll.finalize(self.owner,command),original)
        self.assertEqual(self.payroll.export(self.owner,original['id'],'pdf','1')[0],original_pdf)
        self.assertTrue(validate_integrity(self.office))

    def test_factor_correction_preserves_standard_original_and_exact_retry(self):
        from payroll_factor_2026 import FACTOR_RULE_VERSION
        from business_payroll_statements import project
        data=self.case('regular',500000,tax_class=4,health_additional_percent='2.90',
            tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0)
        command=self.command(data)
        original=self.payroll.finalize(self.owner,command)
        original_pdf=self.payroll.export(self.owner,original['id'],'pdf')[0]
        saved=self.payroll.save_profile(self.owner,dict(request_id=rid(),employee_id=self.employee['id'],
            id=data['profile']['id'],revision=1,profile={**data['profile']['profile'],
                'special_cases':['tax_factor'],'tax_factor':'0.753'},source_file_id=data['file']['id'],
            confirmed=True,correction_reason='Belegten wirksamen ELStAM-Faktor nachgetragen'))
        data['inputs']['profile_revision']=saved['revision']
        correction_command=self.command(data,id=original['id'],revision=1,
            correction_reason='Steuerklasse IV mit belegtem Faktor berichtigt')
        revised=self.payroll.finalize(self.owner,correction_command)
        self.assertEqual(revised['calculation']['rule_version'],FACTOR_RULE_VERSION)
        self.assertEqual(revised['calculation']['individual_wage_tax_minor'],58908)
        self.assertEqual(revised['calculation']['net_minor'],332342)
        self.assertEqual(revised['delta']['employee_tax_minor'],-19333)
        self.assertEqual(revised['delta']['net_minor'],19333)
        self.assertEqual(revised['delta']['employee_social_total_minor'],0)
        self.assertEqual(self.payroll.finalize(self.owner,correction_command),revised)
        self.assertEqual(self.payroll.finalize(self.owner,command),original)
        self.assertEqual(self.payroll.export(self.owner,original['id'],'pdf','1')[0],original_pdf)
        self.assertEqual(project(revised)['calculation']['net_minor'],332342)
        self.assertNotIn('tax_factor',canonical(project(revised)))
        self.assertTrue(validate_integrity(self.office))

    def test_factor_tampering_is_detected_even_with_rehashed_payroll_envelope(self):
        data=self.case('regular',500000,tax_class=4,health_additional_percent='2.90',
            tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0,
            special_cases=['tax_factor'],tax_factor='0.753')
        run=self.payroll.finalize(self.owner,self.command(data))
        row=dict(self.office.db.execute('SELECT * FROM business_payroll_events WHERE id=?',(run['id'],)).fetchone())
        payload=json.loads(row['payload_json'])
        payload['calculation']['tax_parameters']['tax_factor']='0.900'
        payload['preview_hash']=_sha(dict(source=payload['source'],calculation=payload['calculation']))
        envelope={key:row[key] for key in COLUMNS.split(',') if key not in ('payload_json','content_hash')}
        envelope['payload']=payload
        self.office.db.execute('DROP TRIGGER business_payroll_events_update_guard')
        self.office.db.execute('UPDATE business_payroll_events SET payload_json=?,content_hash=? WHERE id=?',
            (canonical(payload),_sha(envelope),run['id']))
        with self.assertRaisesRegex(ValueError,'does not reproduce'):
            validate_integrity(self.office)

    def test_corrected_pension_exemption_creates_delta_and_retains_previous_pdf(self):
        data=self.case()
        command=self.command(data)
        original=self.payroll.finalize(self.owner,command)
        old_pdf=self.payroll.export(self.owner,original['id'],'pdf')[0]
        revised=self.payroll.save_profile(self.owner,dict(request_id=rid(),employee_id=self.employee['id'],
            id=data['profile']['id'],revision=1,profile={**data['profile']['profile'],'minijob_rv_exempt':True},
            source_file_id=data['file']['id'],confirmed=True,correction_reason='Nachweis der wirksamen Befreiung nachgetragen'))
        self.assertEqual(self.payroll.finalize(self.owner,command),original)
        self.problem(409,lambda:self.payroll.preview(self.owner,data['inputs']))
        data['inputs']['profile_revision']=revised['revision']
        correction=self.command(data,id=original['id'],revision=1,correction_reason='Befreiung berücksichtigt')
        updated=self.payroll.finalize(self.owner,correction)
        self.assertEqual(updated['calculation']['net_minor'],60300)
        self.assertEqual(updated['delta']['net_minor'],2171)
        self.assertEqual(updated['delta']['employee_social_total_minor'],-2171)
        self.assertEqual(self.payroll.export(self.owner,original['id'],'pdf','1')[0],old_pdf)
        self.assertEqual(len(self.payroll.get(self.owner,'run',original['id'],True)['items']),2)
        self.assertTrue(validate_integrity(self.office))

    def test_changed_hr_sources_require_a_new_preparation_and_do_not_rewrite_prior_calculation(self):
        data=self.case()
        command=self.command(data)
        original=self.payroll.finalize(self.owner,command)
        self.hr.save_agreement(self.owner,dict(request_id=rid(),employee_id=self.employee['id'],id=data['agreement']['id'],
            revision=1,effective_from='2026-01-01',employment_kind='minijob',pay_basis='monthly',amount_minor=55000,
            currency='EUR',reference_file_id=data['file']['id'],correction_reason='Falsches Vertragsentgelt berichtigt'))
        self.problem(409,lambda:self.payroll.preview(self.owner,data['inputs']))
        self.assertEqual(self.payroll.finalize(self.owner,command),original)
        self.assertEqual(self.payroll.get(self.owner,'run',original['id'])['calculation']['gross_minor'],60300)

    def test_unsupported_or_inconsistent_gross_and_stale_preview_cannot_be_finalized(self):
        data=self.case()
        body=self.command(data)
        mismatch={**data['inputs'],'gross_minor':60000}
        preview=self.payroll.preview(self.owner,mismatch)
        self.assertFalse(preview['can_finalize'])
        self.assertIsNone(preview['calculation']['net_minor'])
        self.assertIn('wage_source_mismatch',[item['code'] for item in preview['calculation']['blockers']])
        with self.assertRaises(Problem) as blocked:
            self.payroll.finalize(self.owner,{**body,'request_id':rid(),'preview_hash':preview['preview_hash'],**mismatch})
        self.assertEqual(blocked.exception.request_resolution,'not_accepted')
        with self.assertRaises(Problem) as stale:
            self.payroll.finalize(self.owner,{**body,'preview_hash':'a'*64})
        self.assertEqual(stale.exception.request_resolution,'not_accepted')
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM business_payroll_events WHERE kind='run'").fetchone()[0],0)

    def test_narrow_fresh_permissions_and_foreign_evidence_are_enforced(self):
        data=self.case()
        command=self.command(data)
        result=self.payroll.finalize(self.owner,command)
        self.assertEqual(self.payroll.get(self.technician,'run',result['id']),result)
        self.problem(403,lambda:self.payroll.export(self.technician,result['id'],'pdf'))
        uid=self.office.add_user('payroll-finance@example.test','Synthetic-finance-password-123','accountant')
        forged=dict(id=uid,role='owner')
        self.problem(403,lambda:self.payroll.records(forged,'run',dict(employee_id=self.employee['id'])))
        self.problem(403,lambda:self.payroll.preview(forged,data['inputs']))
        other=self.planning.save_employee(self.owner,dict(request_id=rid(),user_id=uid,name='Other payroll employee'))
        self.problem(404,lambda:self.payroll.save_profile(self.owner,dict(request_id=rid(),employee_id=other['id'],revision=0,
            profile=profile(),source_file_id=data['file']['id'],confirmed=True)))
        self.office.db.execute('UPDATE users SET active=0 WHERE id=?',(self.owner_id,))
        self.problem(401,lambda:self.payroll.finalize(self.owner,command))

    def test_profile_receipt_never_bypasses_revoked_read_permission(self):
        data=self.case()
        uid=self.office.add_user('payroll-editor@example.test','Synthetic-editor-password-123','accountant')
        editor=dict(id=uid,role='owner')  # Claimed role must never be trusted.
        grants=BusinessFoundation(self.office)
        for name in ('personnel.read','personnel.write'):
            grants.save_grant(self.owner,dict(request_id=rid(),user_id=uid,permission=name,scope='*',effect='allow',revision=0))
        command=dict(request_id=rid(),employee_id=self.employee['id'],id=data['profile']['id'],revision=1,
            profile={**data['profile']['profile'],'verification_note':'Reviewed correction'},source_file_id=data['file']['id'],
            confirmed=True,correction_reason='Reviewed evidence')
        saved=self.payroll.save_profile(editor,command)
        self.assertEqual(self.payroll.save_profile(editor,command),saved)
        grants.save_grant(self.owner,dict(request_id=rid(),user_id=uid,permission='personnel.read',scope='*',effect='deny',revision=1))
        self.problem(403,lambda:self.payroll.save_profile(editor,command))

    def test_rehashed_tampered_result_still_fails_recalculation_on_restore(self):
        data=self.case()
        result=self.payroll.finalize(self.owner,self.command(data))
        row=dict(self.office.db.execute('SELECT * FROM business_payroll_events WHERE id=?',(result['id'],)).fetchone())
        payload=json.loads(row['payload_json'])
        payload['calculation']['net_minor']+=1
        payload['preview_hash']=_sha(dict(source=payload['source'],calculation=payload['calculation']))
        envelope={key:row[key] for key in COLUMNS.split(',') if key not in ('payload_json','content_hash')}
        envelope['payload']=payload
        self.office.db.execute('DROP TRIGGER business_payroll_events_update_guard')
        self.office.db.execute('UPDATE business_payroll_events SET payload_json=?,content_hash=? WHERE id=?',
            (canonical(payload),_sha(envelope),result['id']))
        with self.assertRaisesRegex(ValueError,'does not reproduce'):
            validate_integrity(self.office)

    def test_sqlite_period_replace_and_receipt_failure_are_atomic(self):
        data=self.case()
        command=self.command(data)
        result=self.payroll.finalize(self.owner,command)
        row=dict(self.office.db.execute('SELECT * FROM business_payroll_events WHERE id=?',(result['id'],)).fetchone())
        row['id']=rid()
        with self.assertRaises(sqlite3.IntegrityError):
            self.office.db.execute('INSERT OR REPLACE INTO business_payroll_events('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values()))
        self.assertEqual(self.payroll.get(self.owner,'run',result['id']),result)
        before=self.office.db.execute('SELECT COUNT(*) FROM business_payroll_events').fetchone()[0]
        self.office.db.execute("CREATE TRIGGER synthetic_payroll_receipt_failure BEFORE INSERT ON business_payroll_requests BEGIN SELECT RAISE(ABORT,'synthetic failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.payroll.save_profile(self.owner,dict(request_id=rid(),employee_id=self.employee['id'],id=data['profile']['id'],revision=1,
                profile={**data['profile']['profile'],'minijob_rv_exempt':True},source_file_id=data['file']['id'],confirmed=True,correction_reason='Synthetic correction'))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_payroll_events').fetchone()[0],before)

    def test_original_historical_store_without_payroll_is_accepted_but_partial_install_is_not(self):
        db=sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        old=SimpleNamespace(db=db)
        self.assertTrue(validate_integrity(old))
        db.execute('CREATE TABLE business_payroll_requests(dummy INTEGER)')
        with self.assertRaisesRegex(ValueError,'Incomplete payroll schema'):
            validate_integrity(old)


if __name__=='__main__':
    unittest.main()
