"""Real MFA-bound HTTP payroll cash import and private/public separation."""
import json
import time
import unittest

from business_foundation import BusinessFoundation
from online.auth import totp
from online.test_instance_isolation import MFA_SCHEMA
from online.web import create_app
import test_business_payroll_cash as domain


class PayrollCashHttp(unittest.TestCase):
    def setUp(self):
        self.f=domain.PayrollCashTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.office=self.f.office;self.office.db.executescript(MFA_SCHEMA)
        self.app=create_app(office=self.office,key=self.f.key,host='payroll.example.test',storage=self.f.storage,instance_id=self.f.instance)
        self.client=self.app.test_client();self.token=None
        self.token=self.login('owner@example.test','Synthetic-owner-password-123')

    def call(self,method,path,body=None,*,status=200,token=None):
        response=self.client.open('/api/v1'+path,method=method,base_url='https://payroll.example.test',json=body,
            headers={'Authorization':'Bearer '+(token or self.token)} if token or self.token else {})
        self.assertEqual(response.status_code,status,response.data[:250])
        return response

    def login(self,email,password):
        result=self.call('POST','/login',dict(email=email,password=password)).json
        return self.call('POST','/login/verify',dict(challenge=result['challenge'],code=totp(result['enrollment']['secret'],int(time.time()//30)))).json['token']

    def test_mfa_exact_private_import_finance_classification_and_original_access(self):
        data,run,identity,paid=self.f.case();body=self.f.body(paid)
        sources=self.call('GET','/business/payroll/cash/sources?employee_id='+self.f.f.employee['id']).json
        self.assertTrue(sources['net_sources'][0]['eligible']);self.assertEqual(sources['net_sources'][0]['payments'][0]['amount_minor'],58129)
        original=self.call('GET','/business'+sources['evidence_files'][0]['source_path'])
        self.assertTrue(original.data.startswith(b'%PDF'))
        preview=self.call('POST','/business/payroll/cash/preview',body).json
        command=dict(body,request_id=domain.rid(),preview_hash=preview['preview_hash'],confirmation=True)
        saved=self.call('POST','/business/payroll/cash/batches',command,status=201).json
        self.assertEqual(self.call('POST','/business/payroll/cash/batches',command,status=201).json,saved)
        user=self.office.add_user('payroll-http-finance@example.test','Synthetic-finance-password-123','accountant')
        for permission in ('finance.read','finance.write','accounting.read','accounting.prepare','accounting.admin'):
            BusinessFoundation(self.office).save_grant(self.f.owner,dict(request_id=domain.rid(),user_id=user,permission=permission,effect='allow',scope='*',revision=0))
        token=self.login('payroll-http-finance@example.test','Synthetic-finance-password-123')
        self.call('GET','/business/payroll/cash',token=token,status=403)
        self.call('GET','/business'+sources['evidence_files'][0]['source_path'],token=token,status=403)
        public=self.call('GET','/business/payroll/cash/financial/'+saved['id']+'?revision=1',token=token).json
        self.assertEqual(public,saved['public_source'])
        euer=self.f.euer_body('payroll_cash',self.f.payload(saved));checked=self.call('POST','/business/accounting/euer/preview',euer,token=token).json
        self.call('POST','/business/accounting/euer/confirm',dict(euer,request_id=domain.rid(),preview_hash=checked['preview_hash'],confirmation=True),token=token,status=201)
        report=self.call('GET','/business/accounting/euer/report?year=2026',token=token).json
        self.assertEqual(report['totals']['confirmed_expenses'],'581.29')
        for denied in (self.f.f.employee['id'],paid['id'],identity['id'],data['file']['id'],'12345678903','SYN-WAGE-001'):
            self.assertNotIn(denied,json.dumps(report))

    def test_strict_shape_offline_foreign_binding_and_revoked_permission_preserve_uncertainty(self):
        data,run,identity,paid=self.f.case();body=self.f.body(paid)
        self.call('GET','/business/payroll/cash',{'extra':True},status=400)
        self.call('POST','/business/payroll/cash/preview?extra=1',body,status=400)
        self.call('POST','/business/payroll/cash/preview',dict(body,instance_id=domain.rid()),status=409)
        duplicate=json.dumps(body)[:-1]+',"kind":"remittance"}'
        response=self.client.post('/api/v1/business/payroll/cash/preview',base_url='https://payroll.example.test',data=duplicate,
            content_type='application/json',headers={'Authorization':'Bearer '+self.token})
        self.assertEqual(response.status_code,400)
        device=self.call('POST','/offline/access',{},status=201).json['token']
        self.call('GET','/business/payroll/cash',token=device,status=403)
        command=self.f.command(body);saved=self.call('POST','/business/payroll/cash/batches',command,status=201).json
        with self.office.db:self.office.db.execute("UPDATE users SET role='accountant' WHERE id=?",(self.f.owner['id'],))
        response=self.call('POST','/business/payroll/cash/batches',command,status=403)
        self.assertNotIn('request_resolution',response.json)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_payroll_cash_batches WHERE id=?',(saved['id'],)).fetchone()[0],1)


if __name__=='__main__':unittest.main()
