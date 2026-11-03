"""Actual loopback HTTP and strict private P4 payload/replay boundaries."""
import http.client
from copy import deepcopy
from http.server import ThreadingHTTPServer
import json
import threading
import unittest
from unittest.mock import patch

import business_api
from onedrive import OneDrive
from server import make_handler
import test_business_payroll_entitlements as domain


class PayrollEntitlementsLocalHTTP(domain.monthly.BusinessFixture,unittest.TestCase):
    def setUp(self):
        domain.PayrollEntitlementTests.setUp(self)
        names=business_api.MODULES
        if 'business_payroll_entitlements' not in names:names+=('business_payroll_entitlements',)
        patched=patch.object(business_api,'MODULES',names);patched.start();self.addCleanup(patched.stop)
        self.token=self.office.login('owner@example.test','Synthetic-owner-password-123')
        self.tech_token=self.office.login('technician@example.test','Synthetic-technician-password-123')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.office,OneDrive(self.office)))
        worker=threading.Thread(target=self.server.serve_forever,daemon=True);worker.start()
        self.addCleanup(worker.join);self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)

    def http(self,method,path,data=None,*,status=200,token=None,headers=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        try:
            connection.request(method,'/api/business'+path,json.dumps(data).encode() if data is not None else None,
                {'Authorization':'Bearer '+(token or self.token),'Content-Type':'application/json'}|(headers or {}))
            response=connection.getresponse();raw=response.read();self.assertEqual(response.status,status,raw[:350])
            return json.loads(raw)
        finally:connection.close()

    def test_actual_http_preview_confirm_history_and_lost_ack_after_pause(self):
        sources=self.http('GET','/payroll/entitlements/sources?employee_id='+self.employee['id'])
        self.assertIn(self.original,sources['file_references'])
        request=dict(employee_id=self.employee['id'],employee_revision=self.employee['revision'],kind='unpaid_continuation',
            details=self.details(),source_file_ids=[self.data['file']['id']])
        preview=self.http('POST','/payroll/entitlements/preview',request)
        command=request|dict(request_id=domain.monthly.rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        saved=self.http('POST','/payroll/entitlements',command)
        self.assertEqual(saved,self.http('POST','/payroll/entitlements',command))
        self.assertEqual([saved],self.http('GET','/payroll/entitlements/'+saved['id']+'/history')['items'])
        self.pause();self.assertEqual(saved,self.http('POST','/payroll/entitlements',command))
        self.http('POST','/payroll/entitlements',command|dict(request_id=domain.monthly.rid()),status=423)

    def test_actual_http_rejects_private_self_unknown_body_query_and_oversize(self):
        path='/payroll/entitlements/sources?employee_id='+self.employee['id']
        self.http('GET',path,token=self.tech_token,status=403)
        self.http('GET',path,{},status=400);self.http('GET',path+'&unexpected=1',status=400)
        self.http('POST','/payroll/entitlements?unexpected=1',{},status=400)
        self.http('POST','/payroll/entitlements',{},headers={'Content-Length':'1000001'},status=413)
        body,_=self.request()
        self.http('POST','/payroll/entitlements',body|dict(paid_days=30),status=400)
        self.http('POST','/payroll/entitlements',body,token=self.tech_token,status=403)
        self.assertEqual([],self.http('GET','/payroll/entitlements?employee_id='+self.employee['id'])['items'])

    def test_actual_http_sickness_v2_original_shift_and_lost_ack(self):
        domain.PayrollEntitlementTests.hourly(self)
        details=self.details('sickness_history');source=details['input'];source['pay_basis']='hourly'
        source['episodes'][0].update(**{'from':'2026-11-14','to':'2026-12-31'},
            onset='non_workday',first_scheduled_day='2026-11-16')
        request=dict(employee_id=self.employee['id'],employee_revision=self.employee['revision'],kind='sickness_history',
            details=details,source_file_ids=[self.data['file']['id']])
        preview=self.http('POST','/payroll/entitlements/preview',request)
        self.assertEqual(preview['plan']['rule_version'],'de_2026_sickness_v2')
        self.assertEqual(preview['plan']['episodes'][0]['entitlement_to'],'2026-12-26')
        command=request|dict(request_id=domain.monthly.rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
        saved=self.http('POST','/payroll/entitlements',command)
        self.assertEqual(saved['details']['input']['episodes'][0]['first_scheduled_day'],'2026-11-16')
        self.pause();self.assertEqual(saved,self.http('POST','/payroll/entitlements',command))
        self.assertEqual([saved],self.http('GET','/payroll/entitlements/'+saved['id']+'/history')['items'])

    def test_actual_http_overlapping_v3_and_preemployment_v4_originals(self):
        domain.PayrollEntitlementTests.hourly(self);accepted=[]
        for version in ('de_2026_sickness_phases_v3','de_2026_sickness_start_v4'):
            details=self.details('sickness_history');source=details['input'];source['pay_basis']='hourly';first=source['episodes'][0]
            if version.endswith('v3'):
                first.update(**{'from':'2026-11-14','to':'2026-12-05'},onset='non_workday',first_scheduled_day='2026-11-16')
                source['episodes'].append(dict(deepcopy(first),id=domain.monthly.rid(),continuation_group=domain.monthly.rid(),
                    **{'from':'2026-11-20','to':'2026-12-31'},onset='during_existing_au',first_scheduled_day=None,recovery_before=False))
            else:
                first.update(**{'from':'2026-10-10','to':'2026-12-31'},onset='before_employment')
                source['employment_commencement']=dict(contract_concluded_on='2026-10-01',evidence_refs=[self.original])
            source['prevention_cases']=[dict(id=domain.monthly.rid(),episode_ids=[item['id'] for item in source['episodes']],evidence_refs=[self.original])]
            request=dict(employee_id=self.employee['id'],employee_revision=self.employee['revision'],kind='sickness_history',
                details=details,source_file_ids=[self.data['file']['id']])
            preview=self.http('POST','/payroll/entitlements/preview',request)
            self.assertEqual(preview['plan']['rule_version'],version)
            self.assertEqual(preview['plan']['prevention_cases'][0]['statutory_deadline'],'2026-12-26' if version.endswith('v3') else '2026-12-23')
            command=request|dict(request_id=domain.monthly.rid(),revision=0,status='active',confirmed=True,preview_hash=preview['preview_hash'])
            saved=self.http('POST','/payroll/entitlements',command);accepted.append((saved,command))
            self.assertEqual(details['input'],saved['details']['input'])
        self.pause()
        for saved,command in accepted:
            self.assertEqual(saved,self.http('POST','/payroll/entitlements',command))
            self.assertEqual([saved],self.http('GET','/payroll/entitlements/'+saved['id']+'/history')['items'])


for _name in ('case','identity_details','save_account','account_api','terms_details','body','terms','pause','details','request'):
    setattr(PayrollEntitlementsLocalHTTP,_name,getattr(domain.PayrollEntitlementTests,_name))

if __name__=='__main__':unittest.main()
