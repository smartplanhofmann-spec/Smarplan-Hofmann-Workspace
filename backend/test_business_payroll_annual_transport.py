"""Actual local HTTP for protected annual sources and immutable acceptance."""
import http.client
from http.server import ThreadingHTTPServer
import json
import threading
import unittest
from unittest.mock import patch

import business_api
from onedrive import OneDrive
from server import make_handler
from test_business_payroll import rid
import test_business_payroll_annual_basis as domain


class AnnualPayrollHTTP(unittest.TestCase):
    def setUp(self):
        self.f=domain.PayrollAnnualBasisTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        modules=business_api.MODULES
        if 'business_payroll_annual_basis' not in modules:modules+=('business_payroll_annual_basis',)
        registry=patch.object(business_api,'MODULES',modules);registry.start();self.addCleanup(registry.stop)
        self.token=self.f.office.login('owner@example.test','Synthetic-owner-password-123')
        self.tech_token=self.f.office.login('technician@example.test','Synthetic-technician-password-123')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.f.office,OneDrive(self.f.office)))
        worker=threading.Thread(target=self.server.serve_forever,daemon=True);worker.start()
        self.addCleanup(worker.join);self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)

    def http(self,method,path,data=None,*,status=200,token=None,headers=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        try:
            connection.request(method,'/api/business'+path,json.dumps(data).encode() if data is not None else None,
                {'Authorization':'Bearer '+(token or self.token),'Content-Type':'application/json'}|(headers or {}))
            response=connection.getresponse();raw=response.read();self.assertEqual(response.status,status,raw[:250])
            return json.loads(raw)
        finally:connection.close()

    def workflow(self):
        f=self.f;body=dict(employee_id=f.employee['id'],employee_revision=f.employee['revision'],kind='imported_period',
                          details=f.imported_details(),source_file_ids=[f.original['id']])
        preview=self.http('POST','/payroll/annual-facts/preview',body)
        command=body|dict(request_id=rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        return self.http('POST','/payroll/annual-facts',command),command

    def test_actual_preview_confirm_history_and_exact_replay_after_pause(self):
        saved,command=self.workflow();path='/payroll/annual-facts/'+saved['id']
        self.assertEqual(self.http('GET',path),saved)
        self.assertEqual(self.http('GET',path+'/history')['items'],[saved])
        self.f.pause();self.assertEqual(self.http('POST','/payroll/annual-facts',command),saved)
        self.http('POST','/payroll/annual-facts',command|dict(request_id=rid()),status=423)

    def test_private_sources_strict_queries_methods_bodies_and_size(self):
        path='/payroll/annual-facts/sources?employee_id='+self.f.employee['id']
        catalog=self.http('GET',path)
        for name in ('annual_facts','calculation_cases','payroll_payments','payroll_runs'):
            self.assertEqual(catalog[name],[])
        self.http('GET',path,token=self.tech_token,status=403)
        self.http('GET',path,{},status=400)
        self.http('GET',path+'&ignored=1',status=400)
        self.http('POST','/payroll/annual-facts?ignored=1',{},status=400)
        self.http('POST','/payroll/annual-facts',{},headers={'Content-Length':'1000001'},status=413)
        self.http('DELETE','/payroll/annual-facts',{},status=405)
        saved,body=self.workflow()
        self.http('GET','/payroll/annual-facts/'+saved['id'],token=self.tech_token,status=403)
        self.http('POST','/payroll/annual-facts',body|dict(annual_room_minor=123),status=400)


if __name__=='__main__':unittest.main()
