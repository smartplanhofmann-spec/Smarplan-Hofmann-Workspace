"""Real accepted private Source5 cases, run ownership and separate net transfers."""
from copy import deepcopy
import unittest
from unittest.mock import patch

import business_schema
import business_payroll_multiple_cases as cases
from business_payroll_facts import reference
from core import Problem
from test_business_payroll import rid
import test_payroll_multiple_oneoff_2026 as fixture


class MultipleWorkflow(unittest.TestCase):
    def setUp(self):
        names=business_schema.MODULE_NAMES
        if 'business_payroll_multiple_cases' not in names:names+=('business_payroll_multiple_cases',)
        registry=patch.object(business_schema,'MODULE_NAMES',names);registry.start();self.addCleanup(registry.stop)
        self.c=fixture.CanonicalMultipleComposition('runTest');self.c.setUp();self.addCleanup(self.c.doCleanups)
        self.f=self.c.f;self.source,self.oldsource=self.c.source()
        self.api=cases.PayrollMultipleCases(self.f.office,clock=lambda:self.f.now)

    def details(self):
        source=self.source
        return dict(month=source['month'],running_calculation_case_ref=reference(source['running_calculation_case']),
            components=[dict(component_key=item['component_key'],earning_ref=reference(item['earning']),
                planned_receipts=item['planned_receipts']) for item in source['components']],
            current_annual_basis_ref=reference(source['current_annual_basis']),
            previous_annual_basis_ref=reference(source['previous_annual_basis']) if source['previous_annual_basis'] else None,
            annual_tax_forecasts=[dict(event_key=item['event_key'],annual_tax_forecast_ref=reference(item['annual_tax_forecast'])) for item in source['annual_tax_forecasts']],
            completeness=source['completeness'],verification_note='Actual monthly claims and planned receipts reviewed')

    def case(self,details=None,**changes):
        proposal=dict(employee_id=self.f.employee['id'],employee_revision=self.f.employee['revision'],kind=cases.KIND,
            rule_version=cases.RULE_VERSION,source_contract_version=1,details=details or self.details(),source_file_ids=[self.f.original['id']])
        preview=self.api.preview(self.f.owner,proposal)
        command=proposal|dict(request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])|changes
        return self.api.save(self.f.owner,command),command

    def test_actual_private_case_replay_keeps_sources_and_has_no_run_or_cash_effect(self):
        saved,command=self.case()
        self.assertEqual(saved['sources']['calculation_source'],self.source)
        self.assertEqual(self.api.save(self.f.owner,command),saved)
        self.assertNotIn('accepted_command',saved)
        self.assertEqual(self.api.resolve_multiple_case(self.f.owner,self.f.employee['id'],reference(saved)),saved)
        self.assertEqual(self.f.office.db.execute('SELECT COUNT(*) FROM '+cases.TABLES[2]).fetchone()[0],0)
        self.assertTrue(business_schema.validate_integrity(self.f.office))

    def test_rights_and_duplicate_month_reject_without_acceptance(self):
        saved,command=self.case()
        self.f.problem(409,lambda:self.api.save(self.f.owner,command|dict(request_id=rid())))
        self.f.problem(403,lambda:self.api.get(self.f.technician,saved['id']))
        self.assertEqual(self.f.office.db.execute('SELECT COUNT(*) FROM '+cases.TABLES[1]).fetchone()[0],1)

    def test_revised_actual_forecast_blocks_fresh_source_but_historical_receipt_survives(self):
        saved,command=self.case();forecast=self.source['annual_tax_forecasts'][0]['annual_tax_forecast']
        changed=deepcopy(forecast['details']);changed['verification_note']='Corrected original assessment'
        body,_=self.f.request('annual_tax_forecast',changed)
        self.f.annual.save(self.f.owner,body|dict(id=forecast['id'],revision=forecast['revision'],correction_reason='Revised assessment'))
        self.f.problem(409,lambda:self.api.resolve_multiple_case(self.f.owner,self.f.employee['id'],reference(saved)))
        self.assertEqual(self.api.save(self.f.owner,command),saved)
        self.assertTrue(cases.validate_integrity(self.f.office))

    def run_command(self,case,**changes):
        from test_business_payroll_periods import command
        inputs=dict(source_schema_version=5,employee_id=self.f.employee['id'],multiple_one_off_case_ref=reference(case))
        return command(self.f.payroll,self.f.owner,inputs)|changes

    def test_finalization_atomic_claim_and_original_replay(self):
        case,_=self.case();body=self.run_command(case);run=self.f.payroll.finalize(self.f.owner,body)
        self.assertEqual(run['source']['source_schema_version'],5)
        self.assertEqual(self.f.payroll.finalize(self.f.owner,body),run)
        self.assertTrue(cases.validate_run_consumption(self.f.office,run))
        self.assertEqual(self.f.office.db.execute('SELECT COUNT(*) FROM '+cases.TABLES[2]).fetchone()[0],1)
        self.assertTrue(business_schema.validate_integrity(self.f.office))

    def paid_upgrade(self,*,cash=False):
        from test_business_payroll_periods import command
        from test_business_payroll_accounts import PayrollAccountTests
        f=self.f;inputs=dict(source_schema_version=3,employee_id=f.employee['id'],calculation_case_ref=reference(self.source['running_calculation_case']))
        oldbody=command(f.payroll,f.owner,inputs);old=f.payroll.finalize(f.owner,oldbody)
        running=old['calculation']['net_minor']-old['calculation']['net_deductions_minor']
        parts=[dict(paid_on='2026-10-30',amount_minor=running,payment_reference='ACTUAL-RUNNING-OCTOBER-30')]
        paid,_=f.save_account(f.data,'payment',PayrollAccountTests.payment_details(f,old,f.identity,payments=parts))
        finance=first=None
        if cash:
            from test_business_payroll_calculations import CalculationPayrollWorkflow
            finance=CalculationPayrollWorkflow.finance(self);first=finance.import_cash(finance.body(paid))
        case,_=self.case();body=self.run_command(case,id=old['id'],revision=1,correction_reason='One original bonus after running payment')
        run=f.payroll.finalize(f.owner,body)
        total=run['calculation']['net_minor']-run['calculation']['net_deductions_minor'];bonus=total-running
        parts=parts+[dict(paid_on='2026-10-31',amount_minor=bonus,payment_reference='ACTUAL-BONUS-OCTOBER-31')]
        details=PayrollAccountTests.payment_details(f,run,f.identity,payments=parts)
        details.update(payment_source_schema_version=1,prior_payment_ref=reference(paid),settlement_allocations=[
            dict(payment_index=0,running_minor=running,one_off_allocations=[]),
            dict(payment_index=1,running_minor=0,one_off_allocations=[dict(event_key=self.source['components'][0]['planned_receipts'][0]['event_key'],net_minor=bonus)])])
        newpaid,payment_body=f.save_account(f.data,'payment',details)
        self.assertEqual(newpaid['sources']['single_payment_plan']['preserved_prior_payment_indexes'],[0])
        self.assertEqual(newpaid['sources']['single_payment_plan']['new_payment_indexes'],[1])
        self.assertEqual(f.payroll.finalize(f.owner,oldbody),old)
        self.assertEqual(f.payroll.finalize(f.owner,body),run)
        self.assertEqual(newpaid['details']['payments'][0],paid['details']['payments'][0])
        self.assertTrue(business_schema.validate_integrity(f.office))
        return dict(run=run,old=old,old_payment=paid,payment=newpaid,body=body,payment_body=payment_body,finance=finance,first=first)

    def test_real_paid_v5_upgrade_separate_days_and_original_receipts(self):
        self.paid_upgrade()

    def test_only_new_actual_bonus_part_is_cash_and_euer_once(self):
        from decimal import Decimal
        from core import canonical
        state=self.paid_upgrade(cash=True);finance=state['finance'];f=self.f;payment=state['payment']
        f.problem(409,lambda:finance.api.preview(f.owner,finance.body(payment)))
        body=finance.body(payment);body['sources'][0]['payment_indexes']=[1]
        last=finance.import_cash(body)
        self.assertEqual(last['public_source']['cash_movements'][0]['date'],'2026-10-31')
        self.assertEqual(state['first']['public_source']['cash_movements'][0]['date'],'2026-10-30')
        totals=sum(int(Decimal(value['public_source']['cash_movements'][0]['amount'])*100) for value in (state['first'],last))
        self.assertEqual(totals,state['run']['calculation']['payout_minor'])
        entries=[finance.post('payroll_cash',finance.payload(value)) for value in (state['first'],last)]
        report=finance.euer.report(f.owner,2026)
        self.assertEqual(Decimal(totals)/100,Decimal(report['totals']['confirmed_expenses']))
        public=canonical(dict(entries=entries,report=report,source=last['public_source']))
        for value in (f.employee['id'],state['run']['id'],self.source['components'][0]['component_key'],self.source['components'][0]['planned_receipts'][0]['event_key']):
            self.assertNotIn(value,public)
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_bonus_date_prior_payment_omission_and_unversioned_shape_are_rejected(self):
        state=self.paid_upgrade();f=self.f
        for alteration in ('wrong_day','missing_prior','wrong_contract','new_reference'):
            body=deepcopy(state['payment_body']);body.update(request_id=rid(),id=state['payment']['id'],revision=1,correction_reason='Negative changed source test')
            if alteration=='wrong_day':body['details']['payments'][1]['paid_on']='2026-10-30'
            elif alteration=='missing_prior':body['details']['prior_payment_ref']=None
            elif alteration=='new_reference':body['details']['payments'][0]['payment_reference']='SYN-INVENTED-OLD-TRANSFER'
            else:body['details']['payment_source_schema_version']=True
            with self.subTest(alteration=alteration),self.assertRaises(Problem):
                from business_payroll_accounts import PayrollAccounts
                PayrollAccounts(f.office,clock=lambda:f.now).save(f.owner,body)
        self.assertEqual(f.office.db.execute("SELECT COUNT(*) FROM business_payroll_account_events WHERE kind='payment'").fetchone()[0],2)

    def test_consumption_failure_rolls_back_run_receipt_and_pdf(self):
        case,_=self.case();body=self.run_command(case);f=self.f
        before=f.office.db.execute('SELECT COUNT(*) FROM business_payroll_requests').fetchone()[0]
        with patch('business_payroll_multiple_cases.record_run_consumption',side_effect=Problem(409,'Synthetic claim reservation failure')):
            f.problem(409,lambda:f.payroll.finalize(f.owner,body))
        self.assertEqual(f.payroll._all('run',f.employee['id']),[])
        self.assertEqual(f.office.db.execute('SELECT COUNT(*) FROM business_payroll_requests').fetchone()[0],before)
        self.assertEqual(f.office.db.execute('SELECT COUNT(*) FROM '+cases.TABLES[2]).fetchone()[0],0)
        f.payroll.finalize(f.owner,body)
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_consumption_loss_blocks_read_replay_pdf_ledger_and_restore_validation(self):
        case,_=self.case();body=self.run_command(case);f=self.f;run=f.payroll.finalize(f.owner,body)
        f.office.db.execute('DROP TRIGGER business_payroll_multiple_consumptions_delete_guard')
        f.office.db.execute('DELETE FROM '+cases.TABLES[2])
        for action in (lambda:f.payroll.get(f.owner,'run',run['id']),lambda:f.payroll.finalize(f.owner,body),
                lambda:f.payroll.export(f.owner,run['id'],'pdf'),lambda:f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))):
            with self.assertRaises(Problem):action()
        with self.assertRaises(ValueError):business_schema.validate_integrity(f.office)

    def test_multiple_claim_net_remains_blocked_and_zero_consumption(self):
        self.c.additional(self.source,amount=10000);case,_=self.case();self.assertFalse(case['plan']['payroll_calculation_complete'])
        body=self.run_command(case);self.f.problem(400,lambda:self.f.payroll.finalize(self.f.owner,body))
        self.assertEqual(self.f.office.db.execute('SELECT COUNT(*) FROM '+cases.TABLES[2]).fetchone()[0],0)


    def test_paid_source5_annual_projection_keeps_different_dates_and_prior_bonus_tax(self):
        from payroll_oneoff_composition_2026 import _assignment_profile
        from test_business_payroll_oneoff_annual import OneoffAnnualWorkflow
        from types import SimpleNamespace
        from core import canonical
        state=self.paid_upgrade();f=self.f;wrapper=SimpleNamespace(f=f)
        details=OneoffAnnualWorkflow.basis_details(wrapper,[state['run']],[state['payment']])
        basis,command,_=f.save('annual_basis',details)
        self.assertEqual(basis['plan']['running_taxable_minor'],164516)
        self.assertEqual(basis['plan']['earlier_other_taxable_minor'],50000)
        self.assertEqual(basis['plan']['section_rooms']['regular']['health']['room_minor'],114859)
        compact=basis['sources']['payroll_runs'][0]
        self.assertEqual(compact['projection_format'],'source5_annual_reference_v1')
        self.assertNotIn('calculation',compact)
        profile,_=_assignment_profile(basis,basis['plan']['projection']['periods'][0])
        self.assertEqual(profile,state['run']['source']['profile']['profile'])
        self.assertEqual(basis,f.annual.save(f.owner,command))
        self.assertLess(len(canonical(basis)),250000)
        f.problem(409,lambda:f.request('annual_basis',dict(details,as_of_date='2026-10-30')))
        f.problem(409,lambda:f.request('annual_basis',dict(details,payroll_payment_refs=[])))
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_original_source5_unpaid_revision_keeps_owner_and_cannot_be_downgraded(self):
        from test_business_payroll_periods import command
        f=self.f;case,_=self.case();old=f.payroll.finalize(f.owner,self.run_command(case))
        revised,_=self.case(dict(self.details(),verification_note='Same full claim rechecked'),id=case['id'],revision=1,correction_reason='Reviewed original source again')
        run=f.payroll.finalize(f.owner,self.run_command(revised,id=old['id'],revision=1,correction_reason='Unpaid original revision corrected'))
        rows=f.office.db.execute('SELECT * FROM '+cases.TABLES[2]+' ORDER BY run_revision').fetchall()
        self.assertEqual(rows[0]['claim_identity_key'],self.source['components'][0]['component_key'])
        self.assertIsNone(rows[1]['claim_identity_key']);self.assertIsNone(rows[1]['event_identity_key'])
        running=dict(source_schema_version=3,employee_id=f.employee['id'],calculation_case_ref=reference(self.source['running_calculation_case']))
        body=command(f.payroll,f.owner,running)|dict(id=run['id'],revision=2,correction_reason='Attempted removal of consumed claim')
        f.problem(409,lambda:f.payroll.finalize(f.owner,body))
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_own_source5_projection_uses_explicit_reduced_schema4(self):
        from business_payroll_statements import PayrollStatements,project
        case,_=self.case();run=self.f.payroll.finalize(self.f.owner,self.run_command(case))
        self.assertEqual(4,project(run)['schema_version'])
        statement=PayrollStatements(self.f.office).get(self.f.technician,run['id'])['statement']
        self.assertEqual('not_evidenced_by_calculation',statement['payment_status'])
        self.assertNotIn('multiple_one_off_details',statement['calculation'])

    def test_private_ledger_and_pdf_expose_versioned_source5_evidence(self):
        state=self.paid_upgrade();f=self.f
        ledger=f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026'))['ledger']
        self.assertEqual(ledger['schema_version'],4)
        self.assertTrue(ledger['months'][9]['wage_account']['complete'])
        self.assertEqual(ledger['recorded_multiple_one_off_payments'][0]['run_ref'],reference(state['run']))
        self.assertIn(b'Sonstiger Bezug',f.payroll.export(f.owner,state['run']['id'],'pdf')[0])
        for format_ in ('json','csv','pdf'):
            content,_=f.payroll.export_ledger(f.owner,dict(employee_id=f.employee['id'],year='2026',snapshot_hash=ledger['snapshot_hash']),format_)
            self.assertTrue(content)

    def test_actual_following_month_uses_compact_paid_source5_tax_and_social_room(self):
        from test_business_payroll_oneoff_annual import OneoffAnnualWorkflow
        from test_business_payroll_oneoff_runs import OneoffRunWorkflow
        from business_payroll_oneoff_cases import PayrollOneoffCases
        state=self.paid_upgrade();f=self.f;f.now=f.now.replace(month=12,day=31)
        old=OneoffRunWorkflow('runTest');old.f=f;old.source=self.oldsource
        old.api=PayrollOneoffCases(f.office,clock=lambda:f.now)
        wrapper=OneoffAnnualWorkflow('runTest');wrapper.f=f;wrapper.w=old
        with patch('business_personnel_workflow.datetime') as clock:
            clock.now.side_effect=lambda zone:f.now
            case,_,run,payment,basis,_=wrapper.successor('2026-11',[state['run']],[state['payment']])
            self.assertEqual(basis['sources']['payroll_runs'][0]['projection_format'],'source5_annual_reference_v1')
            self.assertEqual(basis['plan']['earlier_other_taxable_minor'],50000)
            self.assertEqual(basis['plan']['running_taxable_minor'],464516)
            self.assertEqual(basis['plan']['section_rooms']['regular']['health']['room_minor'],396109)
            source,_=self.c.source(original_source=case['sources']['calculation_source'])
            result=fixture.calculate(source)
            self.assertEqual(result['net_minor'],run['calculation']['net_minor'])
            self.assertEqual(case['sources']['calculation_source']['annual_tax_forecast']['plan']['annual_pay_before_minor'],814516)
            self.assertTrue(business_schema.validate_integrity(f.office))

    def test_source5_payment_receipt_loss_blocks_replay_cash_ledger_and_restore(self):
        from business_payroll_accounts import PayrollAccounts
        from test_business_payroll_calculations import CalculationPayrollWorkflow
        state=self.paid_upgrade();f=self.f;finance=CalculationPayrollWorkflow.finance(self)
        accounts=PayrollAccounts(f.office,clock=lambda:f.now)
        f.office.db.execute('DROP TRIGGER business_payroll_account_requests_delete_guard')
        f.office.db.execute('DELETE FROM business_payroll_account_requests WHERE request_id=?',(state['payment_body']['request_id'],))
        for action in (lambda:accounts.save(f.owner,state['payment_body']),lambda:accounts.get(f.owner,state['payment']['id']),lambda:accounts.records(f.owner,dict(employee_id=f.employee['id'])),
                lambda:f.payroll.ledger(f.owner,dict(employee_id=f.employee['id'],year='2026')),
                lambda:finance.api.preview(f.owner,finance.body(state['payment']))):
            with self.assertRaises(Problem):action()
        with self.assertRaises(ValueError):business_schema.validate_integrity(f.office)


if __name__=='__main__':unittest.main()
