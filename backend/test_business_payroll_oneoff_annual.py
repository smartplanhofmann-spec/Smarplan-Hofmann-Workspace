"""Actual paid v6 successors: no reused contribution room or lost annual tax."""
import calendar
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import business_schema
from business_payroll_annual_basis import validate_annual_sources
from business_payroll_calculation_cases import PayrollCalculationCases, CALCULATION_RULE_VERSION
from business_payroll_facts import reference
from business_personnel_workflow import _sha
from core import Problem, canonical
from payroll_annual_basis_2026 import build_annual_plan
from payroll_oneoff_composition_2026 import _assignment_profile
from test_business_payroll import rid
import test_business_payroll_oneoff_runs as fixture


class OneoffAnnualWorkflow(unittest.TestCase):
    def setUp(self):
        self.w=fixture.OneoffRunWorkflow('runTest');self.w.setUp();self.addCleanup(self.w.doCleanups)
        self.f=self.w.f;self.f.now=self.f.now.replace(month=12,day=31)
        clock=patch('business_personnel_workflow.datetime');mock=clock.start();self.addCleanup(clock.stop)
        mock.now.side_effect=lambda zone:self.f.now

    def first(self,**changes):
        case,body=self.w.workflow(**changes)
        run=self.f.payroll.finalize(self.f.owner,self.w.command(case))
        payment,payment_command=self.w.payment(run)
        return case,body,run,payment

    def basis_details(self,runs,payments,*,month='2026-10',as_of_date='2026-11-01',current=None):
        f=self.f;end=month+f'-{calendar.monthrange(2026,int(month[-2:]))[1]:02}'
        first_month=(runs[0]['source']['month'] if runs else current['details']['month'])
        before=int(first_month[-2:])-1
        gaps=[] if not before else [dict(start='2026-01-01',end=f'2026-{before:02}-{calendar.monthrange(2026,before)[1]:02}',
            reason='not_employed',evidence_ref=f.original)]
        return f.basis_details(runs[0] if runs else current,imported_period_refs=[],
            payroll_run_refs=[reference(value) for value in runs],payroll_payment_refs=[reference(value) for value in payments],
            current_calculation_case_ref=reference(current) if current else None,coverage_to=end,as_of_date=as_of_date,
            gaps=gaps)

    def successor(self,month,runs,payments,*,bonus=50000):
        f=self.f;end=month+f'-{calendar.monthrange(2026,int(month[-2:]))[1]:02}'
        terms=self.w.source['running_calculation_case']['sources']['employment_terms'][0]
        preview=f.hr.preview(f.owner,dict(employee_id=f.employee['id'],month=month))
        f.data['preparation']=f.hr.close_preparation(f.owner,dict(request_id=rid(),employee_id=f.employee['id'],
            month=month,revision=0,source_hash=preview['source_hash'],completeness_confirmed=True))
        pd=f.period_details(terms,month=month);pv=f.api.preview(f.owner,f.preview_body(pd))
        base=f.api.save(f.owner,f.body('period_case',pd,preview_hash=pv['preview_hash']))
        api=PayrollCalculationCases(f.office,clock=lambda:f.now)
        details=dict(month=month,period_case_ref=reference(base),employment_terms_refs=[reference(terms)],
            profile_refs=[reference(f.data['profile'])],identity_refs=[reference(f.identity)],segment_events=[],
            thirty_day_rule=None,entitlement_case_refs=[],travel_settlement_refs=[],flat_tax_decision=None,
            verification_note='Actual following month based on unchanged protected contract')
        request=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind='calculation_case',
            rule_version=CALCULATION_RULE_VERSION,source_contract_version=1,details=details,source_file_ids=[f.original['id']])
        preview=api.preview(f.owner,request)
        current=api.save(f.owner,request|dict(request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash']))
        annual,annual_command,_=f.save('annual_basis',self.basis_details(runs,payments,month=month,as_of_date=end,current=current))
        ed=f.claim_details(terms,reference_text='Separate actual bonus '+month)
        ed.update(planned_receipt_date=end,amount_minor=bonus,claim_periods=[dict(start=month+'-01',end=end,evidence_ref=f.original)])
        earning,_,_=f.save('one_off_earning',ed)
        fd=f.forecast_details(annual,earning,terms);fd.update(receipt_date=end,
            remaining_periods=[dict(month=f'2026-{index:02}',employment_terms_ref=reference(terms),
                agreement_refs=[reference(f.data['agreement'])],work_schedule_ref=None) for index in range(int(month[-2:])+1,13)])
        forecast,_,_=f.save('annual_tax_forecast',fd)
        previous=self.w.source['previous_annual_basis']
        if previous is not None:
            previous_details=deepcopy(previous['details']);previous_details.update(as_of_date=end,
                payroll_run_refs=[reference(value) for value in runs if value['calculation']['one_off_details']['assignment']['social_year']==2025],
                payroll_payment_refs=[reference(value) for value in payments if any(run['id']==value['details']['run_id']
                    and run['calculation']['one_off_details']['assignment']['social_year']==2025 for run in runs)])
            previous,_,_=f.save('annual_basis',previous_details)
        self.w.source=dict(self.w.source,month=month,running_calculation_case=current,one_off_earning=earning,
            current_annual_basis=annual,annual_tax_forecast=forecast,previous_annual_basis=previous)
        details=self.w.details();details['previous_annual_basis_ref']=reference(previous) if previous else None
        body,_=self.w.request(details);case=self.w.api.save(f.owner,body)
        run=self.f.payroll.finalize(f.owner,self.w.command(case));payment,_=self.w.payment(run)
        return case,body,run,payment,annual,annual_command

    def test_actual_paid_composition_contributes_running_and_bonus_separately(self):
        f=self.f;case,body,run,payment=self.first()
        basis,command,_=f.save('annual_basis',self.basis_details([run],[payment]))
        self.assertEqual((basis['plan']['running_taxable_minor'],basis['plan']['earlier_other_taxable_minor']),(164516,50000))
        self.assertEqual(basis['plan']['section_rooms']['regular']['health']['room_minor'],114859)
        self.assertEqual(basis['plan']['projection']['prior_one_offs'][0]['bases_minor'],dict.fromkeys(('health','care','pension','unemployment'),50000))
        compact=basis['sources']['payroll_runs'][0]
        self.assertEqual(compact['projection_format'],'source4_annual_reference_v1')
        self.assertNotIn('calculation',compact);self.assertNotIn('sources',basis['sources']['payroll_payments'][0])
        period=basis['plan']['projection']['periods'][0];profile,social=_assignment_profile(basis,period)
        self.assertEqual(profile,run['source']['calculation_case']['sources']['profiles'][0]['profile'])
        self.assertEqual(social['health_additional_percent'],'2.900')
        self.assertEqual(f.annual.save(f.owner,command),basis)
        self.assertEqual(self.w.api.save(f.owner,body),case)
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_unpaid_omitted_later_or_replaced_actual_source_cannot_be_zero(self):
        f=self.f;case,_=self.w.workflow();run=f.payroll.finalize(f.owner,self.w.command(case))
        f.problem(409,lambda:f.request('annual_basis',self.basis_details([run],[])))
        payment,_=self.w.payment(run)
        f.problem(409,lambda:f.request('annual_basis',self.basis_details([run],[])))
        f.problem(409,lambda:f.request('annual_basis',self.basis_details([run],[payment],as_of_date='2026-10-30')))
        omitted=self.basis_details([],[],current=case['sources']['calculation_source']['running_calculation_case'])
        omitted.update(current_calculation_case_ref=None,gaps=[dict(start='2026-01-01',end='2026-10-31',reason='not_employed',evidence_ref=f.original)])
        f.problem(409,lambda:f.request('annual_basis',omitted))

    def test_second_claim_same_month_does_not_hide_first_bonus(self):
        f=self.f;case,body,run,payment=self.first()
        source=case['sources']['calculation_source'];terms=source['running_calculation_case']['sources']['employment_terms'][0]
        earning,_,_=f.save('one_off_earning',f.claim_details(terms,reference_text='Separate additional October claim'))
        forecast,_,_=f.save('annual_tax_forecast',f.forecast_details(source['current_annual_basis'],earning,terms))
        details=self.w.details()|dict(one_off_earning_ref=reference(earning),annual_tax_forecast_ref=reference(forecast))
        with self.assertRaises(Problem) as rejected:self.w.request(details)
        self.assertEqual(rejected.exception.status,409);self.assertIn('Mehrfachbezugsrechnung',rejected.exception.message)
        # Re-reading the original accepted receipt remains valid.
        self.assertEqual(self.w.api.save(f.owner,body),case)

    def test_rehashed_compact_historical_profile_cannot_replace_verified_original(self):
        f=self.f;_,_,run,payment=self.first()
        basis,_,_=f.save('annual_basis',self.basis_details([run],[payment]))
        self.assertTrue(validate_annual_sources(f.office,basis))
        row=dict(f.annual._row(basis['id']));payload=json.loads(row['payload_json']);sources=json.loads(row['sources_json'])
        sources['internal_periods'][0]['assignment_profiles'][0]['profile']['health_additional_percent']='0.000'
        payload['plan']=build_annual_plan(sources);payload['preview_hash']=_sha(dict(source_snapshot=sources,plan=payload['plan']))
        payload['accepted_command']['preview_hash']=payload['preview_hash']
        envelope={key:value for key,value in row.items() if key not in ('payload_json','sources_json','content_hash')}
        envelope.update(payload=payload,sources=sources,source_hash=_sha(sources),
            command_hash=_sha(['annual.saved:annual_basis',payload['accepted_command']]))
        content_hash=_sha(envelope)
        for table in ('business_payroll_annual_events','business_payroll_annual_requests'):
            f.office.db.execute('DROP TRIGGER '+table+'_update_guard')
        f.office.db.execute('UPDATE business_payroll_annual_events SET payload_json=?,sources_json=?,source_hash=?,command_hash=?,content_hash=? WHERE id=?',
            (canonical(payload),canonical(sources),envelope['source_hash'],envelope['command_hash'],content_hash,basis['id']))
        f.office.db.execute('UPDATE business_payroll_annual_requests SET request_hash=?,fact_content_hash=? WHERE fact_id=?',
            (envelope['command_hash'],content_hash,basis['id']))
        forged=f.annual._get(basis['id'])
        with self.assertRaises(ValueError):validate_annual_sources(f.office,forged)
        with self.assertRaises(ValueError):business_schema.validate_integrity(f.office)

    def test_three_actual_bonuses_keep_tax_and_social_room_and_bounded_sources(self):
        f=self.f;case,body,run,payment=self.first();original_case=deepcopy(case)
        runs=[run];payments=[payment];sizes=[len(canonical(run).encode())]
        for index,month in enumerate(('2026-11','2026-12'),1):
            case,_,run,payment,basis,_=self.successor(month,runs,payments)
            self.assertEqual(basis['plan']['earlier_other_taxable_minor'],index*50000)
            self.assertEqual(basis['plan']['running_taxable_minor'],164516+index*300000)
            self.assertEqual(len(basis['plan']['projection']['prior_one_offs']),index)
            self.assertEqual(basis['plan']['section_rooms']['regular']['health']['room_minor'],(396109,627359)[index-1])
            expected_before=164516+600000+index*50000
            self.assertEqual(case['sources']['calculation_source']['annual_tax_forecast']['plan']['annual_pay_before_minor'],expected_before)
            runs.append(run);payments.append(payment);sizes.append(len(canonical(run).encode()))
        self.assertLess(sizes[-1],sizes[0]*2)
        self.assertLess(sizes[-1]-sizes[-2],35000)
        self.assertEqual(self.w.api.save(f.owner,body),original_case)
        self.assertTrue(business_schema.validate_integrity(f.office))
        source_bytes=len(canonical(self.w.api.sources(f.owner,dict(employee_id=f.employee['id'],month='2026-12'))).encode())
        self.assertLess(source_bytes,4*1024*1024)
        print('SOURCE4_SUCCESSOR_SIZES_BYTES',sizes)
        print('SOURCE4_THREE_MONTH_SOURCE_CATALOG_BYTES',source_bytes)

    def test_march_clause_receipt_consumes_only_actual_previous_social_year(self):
        f=self.f;self.w.source=self.w.c.source(january=True,bonus=200000,previous=True)
        details=self.w.details();details['previous_annual_basis_ref']=reference(self.w.source['previous_annual_basis'])
        body,_=self.w.request(details);case=self.w.api.save(f.owner,body)
        run=f.payroll.finalize(f.owner,self.w.command(case));payment,_=self.w.payment(run)
        old=self.w.source['previous_annual_basis'];d=deepcopy(old['details'])
        d.update(as_of_date='2026-02-01',payroll_run_refs=[reference(run)],payroll_payment_refs=[reference(payment)])
        prior,_,_=f.save('annual_basis',d)
        self.assertEqual(prior['plan']['running_taxable_minor'],200000)
        self.assertEqual(prior['plan']['earlier_other_taxable_minor'],0)
        self.assertEqual(prior['plan']['section_rooms']['regular']['health']['room_minor'],151250)
        self.assertEqual(len(prior['plan']['projection']['prior_one_offs']),1)
        d=f.basis_details(run,coverage_to='2026-01-31',as_of_date='2026-02-01',imported_period_refs=[],
            payroll_run_refs=[reference(run)],payroll_payment_refs=[reference(payment)],gaps=[])
        current,_,_=f.save('annual_basis',d)
        self.assertEqual(current['plan']['earlier_other_taxable_minor'],200000)
        self.assertEqual(current['plan']['projection']['prior_one_offs'],[])
        self.assertEqual(current['plan']['running_taxable_minor'],164516)
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_march_clause_correction_replaces_own_bonus_without_reusing_other_room(self):
        f=self.f;self.w.source=self.w.c.source(january=True,bonus=200000,previous=True)
        details=self.w.details();details['previous_annual_basis_ref']=reference(self.w.source['previous_annual_basis'])
        body,_=self.w.request(details);case=self.w.api.save(f.owner,body)
        run=f.payroll.finalize(f.owner,self.w.command(case));payment,_=self.w.payment(run)
        self.assertEqual(case,self.w.api.resolve_one_off_case(f.owner,f.employee['id'],reference(case)))
        earning=self.w.source['one_off_earning'];ed=earning['details']|dict(amount_minor=210000)
        command,_=f.request('one_off_earning',ed)
        revised=f.annual.save(f.owner,command|dict(id=earning['id'],revision=1,correction_reason='Actual original January claim corrected'))
        forecast=self.w.source['annual_tax_forecast'];fd=forecast['details']|dict(current_one_off_ref=reference(revised))
        command,_=f.request('annual_tax_forecast',fd)
        forecast=f.annual.save(f.owner,command|dict(id=forecast['id'],revision=1,correction_reason='January forecast binds corrected same claim'))
        details=details|dict(one_off_earning_ref=reference(revised),annual_tax_forecast_ref=reference(forecast))
        command,_=self.w.request(details,id=case['id'],revision=1,correction_reason='Same January claim; preserve original 2025 assignment')
        corrected=self.w.api.save(f.owner,command)
        self.assertEqual(corrected['plan']['one_off_details']['assignment']['bases_minor']['health'],210000)
        current=f.payroll.finalize(f.owner,self.w.command(corrected,id=run['id'],revision=1,correction_reason='Actual January claim corrected without second consumption'))
        delta=current['calculation']['payout_minor']-run['calculation']['payout_minor'];self.assertGreater(delta,0)
        revised_payment,_=self.w.payment(current,payments=payment['details']['payments']+[
            dict(paid_on='2026-01-31',amount_minor=delta,payment_reference='SYN-MARCH-CORRECTION-DELTA')])
        d=deepcopy(self.w.source['previous_annual_basis']['details'])
        d.update(as_of_date='2026-02-01',payroll_run_refs=[reference(current)],payroll_payment_refs=[reference(revised_payment)])
        prior,_,_=f.save('annual_basis',d)
        self.assertEqual(prior['plan']['section_rooms']['regular']['health']['room_minor'],141250)
        self.assertEqual(len(prior['plan']['projection']['prior_one_offs']),1)
        self.assertEqual(self.w.api.save(f.owner,body),case)
        self.assertTrue(business_schema.validate_integrity(f.office))

    def test_second_march_clause_bonus_consumes_only_remaining_previous_year_room(self):
        f=self.f;self.w.source=self.w.c.source(january=True,bonus=200000,previous=True)
        details=self.w.details();details['previous_annual_basis_ref']=reference(self.w.source['previous_annual_basis'])
        body,_=self.w.request(details);case=self.w.api.save(f.owner,body)
        run=f.payroll.finalize(f.owner,self.w.command(case));payment,_=self.w.payment(run)
        case,_,second,paid,basis,_=self.successor('2026-02',[run],[payment],bonus=500000)
        self.assertEqual(basis['plan']['earlier_other_taxable_minor'],200000)
        extra=second['calculation']['one_off_details']
        self.assertEqual(extra['assignment']['social_year'],2025)
        self.assertEqual(extra['assignment']['bases_minor']['health'],151250)
        self.assertEqual(case['sources']['calculation_source']['annual_tax_forecast']['plan']['annual_pay_before_minor'],3664516)
        previous=self.w.source['previous_annual_basis'];d=deepcopy(previous['details'])
        d.update(as_of_date='2026-03-01',payroll_run_refs=[reference(run),reference(second)],payroll_payment_refs=[reference(payment),reference(paid)])
        closed,_,_=f.save('annual_basis',d)
        self.assertEqual(closed['plan']['section_rooms']['regular']['health']['room_minor'],0)
        self.assertEqual(len(closed['plan']['projection']['prior_one_offs']),2)
        self.assertTrue(business_schema.validate_integrity(f.office))


if __name__=='__main__':unittest.main()
