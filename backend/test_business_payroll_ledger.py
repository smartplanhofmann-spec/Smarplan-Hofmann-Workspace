"""Yearly effective-revision sums, deterministic exports and fresh access."""
import csv
import io
import json
import unittest

import test_business_payroll as monthly
from business_personnel_workflow import _sha
from business_payroll import dispatch
from core import canonical


class PayrollLedgerTests(monthly.BusinessFixture,unittest.TestCase):
    setUp=monthly.PayrollWorkflowTests.setUp
    case=monthly.PayrollWorkflowTests.case
    command=monthly.PayrollWorkflowTests.command

    def next_month(self,data,month):
        preview=self.hr.preview(self.owner,dict(employee_id=self.employee['id'],month=month))
        preparation=self.hr.close_preparation(self.owner,dict(request_id=monthly.rid(),employee_id=self.employee['id'],
            month=month,revision=0,source_hash=preview['source_hash'],completeness_confirmed=True))
        return {**data,'preparation':preparation,'inputs':{**data['inputs'],'preparation_id':preparation['id'],'preparation_revision':preparation['revision']}}

    def overview(self,actor=None,year='2026'):
        return self.payroll.ledger(actor or self.owner,dict(employee_id=self.employee['id'],year=year))

    def test_effective_revisions_sum_once_and_all_exports_match_preview_manifest(self):
        data=self.case('regular',500000,health_additional_percent='2.90',tax_allowance_monthly_minor=0,tax_addition_monthly_minor=0)
        first=self.payroll.finalize(self.owner,self.command(data))
        following=self.next_month(data,'2026-11')
        second=self.payroll.finalize(self.owner,self.command(following))
        previous=self.overview()
        revised=self.payroll.save_profile(self.owner,dict(request_id=monthly.rid(),employee_id=self.employee['id'],
            id=data['profile']['id'],revision=1,profile={**data['profile']['profile'],'tax_allowance_monthly_minor':20000},
            source_file_id=data['file']['id'],confirmed=True,correction_reason='Synthetic documented allowance'))
        data['inputs']['profile_revision']=revised['revision']
        corrected=self.payroll.finalize(self.owner,self.command(data,id=first['id'],revision=1,correction_reason='=1+1'))
        self.problem(409,lambda:self.payroll.export_ledger(self.owner,dict(employee_id=self.employee['id'],year='2026',
            snapshot_hash=previous['ledger']['snapshot_hash']),'pdf'))
        response=self.overview(); ledger=response['ledger']
        self.assertEqual(ledger['recorded_months'],2)
        self.assertEqual(ledger['totals']['gross_minor'],1000000)
        self.assertEqual(ledger['totals']['net_minor'],corrected['calculation']['net_minor']+second['calculation']['net_minor'])
        self.assertEqual(ledger['totals']['employee_social_total_minor'],217500)
        self.assertEqual(ledger['totals']['employee_contributions']['health_general'],73000)
        self.assertEqual(ledger['totals']['employer_levies']['u1'],21000)
        self.assertEqual(len(ledger['correction_history']),1)
        self.assertEqual(ledger['correction_history'][0]['delta'],corrected['delta'])
        self.assertEqual(ledger['months'][9]['revision'],2)
        self.assertEqual(ledger['months'][10]['revision'],1)
        self.assertEqual(len(ledger['missing_months']),10)
        self.assertTrue(ledger['tax_totals_complete'])
        self.assertFalse(ledger['annual_totals_complete'])
        self.assertFalse(ledger['statutory_wage_account_complete'])
        self.assertEqual(ledger['statutory_report_status'],'not_transmitted')
        self.assertEqual(ledger['snapshot_hash'],_sha({key:value for key,value in ledger.items() if key!='snapshot_hash'}))
        self.assertEqual(self.overview(),response)  # PDF invariant mode, no current timestamp in snapshot.
        for format_ in ('json','csv','pdf'):
            content,mime=self.payroll.export_ledger(self.owner,dict(employee_id=self.employee['id'],year='2026',
                snapshot_hash=ledger['snapshot_hash']),format_)
            proof=response['exports'][format_]
            self.assertEqual(_sha(content),proof['sha256'])
            self.assertEqual(len(content),proof['size'])
            self.assertEqual(mime,proof['media_type'])
            self.assertEqual(content.filename,proof['filename'])
            if format_=='json':
                self.assertEqual(bytes(content),canonical(ledger).encode())
                self.assertEqual(json.loads(content),ledger)
            elif format_=='csv':
                rows=list(csv.reader(io.StringIO(content.decode('utf-8-sig')),delimiter=';'))
                correction=next(row for row in rows if row[0]=='correction')
                self.assertEqual(correction[-1],"'=1+1")
                self.assertEqual(correction[2],'not_added_to_totals')
            else:
                self.assertTrue(content.startswith(b'%PDF-'))
        self.assertEqual(self.overview(),response)  # Export audit does not change source snapshot.

    def test_partial_regular_month_keeps_tax_net_totals_unknown(self):
        data=self.case('regular',500000,health_additional_percent='2.90')
        self.payroll.finalize(self.owner,self.command(data))
        ledger=self.overview()['ledger']
        self.assertEqual(ledger['partial_months'],['2026-10'])
        self.assertFalse(ledger['tax_totals_complete'])
        self.assertFalse(ledger['annual_totals_complete'])
        self.assertEqual(ledger['totals']['gross_minor'],500000)
        self.assertEqual(ledger['totals']['employee_social_total_minor'],108750)
        for key in ('net_minor','payout_minor','employee_tax_minor','individual_wage_tax_minor','solidarity_minor','church_tax_minor'):
            self.assertIsNone(ledger['totals'][key],key)

    def test_complete_minijob_year_and_missing_year_are_distinguished(self):
        data=self.case()
        for number in range(1,13):
            selected=data if number==10 else self.next_month(data,'2026-'+str(number).zfill(2))
            self.payroll.finalize(self.owner,self.command(selected))
        ledger=self.overview()['ledger']
        self.assertTrue(ledger['calendar_year_complete'])
        self.assertTrue(ledger['annual_totals_complete'])
        self.assertEqual(ledger['missing_months'],[])
        self.assertEqual(ledger['totals']['gross_minor'],723600)
        self.assertEqual(ledger['totals']['net_minor'],58129*12)
        self.assertEqual(ledger['totals']['employer_flat_tax_minor'],1206*12)
        self.assertEqual(ledger['totals']['individual_wage_tax_minor'],0)
        self.assertIsNone(ledger['months'][0]['calculation']['individual_wage_tax_minor'])
        empty=self.overview(year='2025')['ledger']
        self.assertEqual(empty['recorded_months'],0)
        self.assertEqual(len(empty['missing_months']),12)
        self.assertFalse(empty['tax_totals_complete'])
        self.assertIsNone(empty['totals']['gross_minor'])
        self.assertIsNone(empty['totals']['employee_contributions']['pension'])

    def test_fresh_access_and_export_scope_and_strict_queries(self):
        data=self.case()
        self.payroll.finalize(self.owner,self.command(data))
        result=self.overview()
        self.assertEqual(self.overview(self.technician),result)
        query=dict(employee_id=self.employee['id'],year='2026',snapshot_hash=result['ledger']['snapshot_hash'])
        self.problem(403,lambda:self.payroll.export_ledger(self.technician,query,'json'))
        uid=self.office.add_user('ledger-accountant@example.test','Synthetic-ledger-password-123','accountant')
        self.problem(403,lambda:self.overview(dict(id=uid,role='owner')))
        self.problem(400,lambda:self.payroll.ledger(self.owner,dict(employee_id=self.employee['id'],year=True)))
        self.problem(400,lambda:self.payroll.export_ledger(self.owner,{key:value for key,value in query.items() if key!='snapshot_hash'},'pdf'))
        result_,status,_=dispatch(self.office,self.owner,'/payroll/ledger','GET',{'_query':dict(employee_id=self.employee['id'],year='2026')})
        self.assertEqual(status,200);self.assertEqual(result_,result)
        self.problem(405,lambda:dispatch(self.office,self.owner,'/payroll/ledger','POST',{}))
        self.office.db.execute('UPDATE users SET active=0 WHERE id=?',(self.owner_id,))
        self.problem(401,lambda:self.payroll.export_ledger(self.owner,query,'json'))


if __name__=='__main__':
    unittest.main()
