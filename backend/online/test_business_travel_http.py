"""Actual application MFA/HTTP travel routes, framing and privacy boundaries."""
import json
import hashlib
import time
import unittest

import test_business_travel_allowances as domain
from business_foundation import BusinessFoundation
from online.auth import totp
from online.test_instance_isolation import MFA_SCHEMA
from online.web import create_app


class TravelHttpTests(unittest.TestCase):
    def setUp(self):
        self.f=domain.TravelWorkflowTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.office=self.f.office;self.office.db.executescript(MFA_SCHEMA)
        self.app=create_app(office=self.office,key=self.f.key,host='travel.example.test',storage=self.f.storage,instance_id=self.f.instance)
        self.client=self.app.test_client();self.token=None
        self.token=self.login('owner@example.test','Synthetic-owner-password-123')
        self.tech=self.login('technician@example.test','Synthetic-technician-password-123')
    def call(self,method,path,body=None,*,status=200,token=None):
        chosen=token or self.token
        response=self.client.open('/api/v1'+path,method=method,base_url='https://travel.example.test',json=body,
            headers={'Authorization':'Bearer '+chosen} if chosen else {})
        self.assertEqual(response.status_code,status,response.data[:350]);return response
    def login(self,email,password):
        first=self.call('POST','/login',dict(email=email,password=password)).json
        return self.call('POST','/login/verify',dict(challenge=first['challenge'],code=totp(first['enrollment']['secret'],int(time.time()//30)))).json['token']
    def test_http_trip_fremdpruefung_originals_payment_and_public_finance(self):
        rates=self.call('GET','/business/personnel/travel/catalog',token=self.tech).json
        self.assertEqual(len(rates['rates']),215)
        sources=self.call('GET','/business/personnel/travel/sources?employee_id='+self.f.employee['id'],token=self.tech).json
        self.assertTrue(sources['rights']['write']);self.assertFalse(sources['rights']['approve'])
        body=self.f.trip_body();saved=self.call('POST','/business/personnel/travel/trips',body,token=self.tech).json
        self.assertEqual(self.call('GET','/business/personnel/travel/requests/'+body['request_id'],token=self.tech).json,saved)
        detail=self.call('GET','/business/personnel/travel/trips/'+body['id'],token=self.tech).json
        submit=dict(request_id=domain.rid(),employee_id=self.f.employee['id'],revision=detail['item']['revision'],source_hash=detail['source_hash'],confirmed=True)
        submitted=self.call('POST','/business/personnel/travel/trips/'+body['id']+'/submit',submit,token=self.tech).json
        approval=self.f.approval(submitted['result'])
        preview_body={k:v for k,v in approval.items() if k not in ('id','request_id','revision','source_hash','preview_hash','confirmed')}
        preview=self.call('POST','/business/personnel/travel/settlements/preview',preview_body).json
        self.assertEqual(preview['preview_hash'],approval['preview_hash'])
        settlement=self.call('POST','/business/personnel/travel/settlements',approval).json['result']
        exported=self.call('GET','/business/personnel/travel/settlements/'+settlement['id']+'/export?format=pdf&revision=1')
        self.assertTrue(exported.data.startswith(b'%PDF'))
        payment=self.f.payment(settlement);accepted=self.call('POST','/business/personnel/travel/payments',payment).json
        user=self.office.add_user('finance@travel.example.test','Synthetic-finance-password-123','accountant')
        for permission in ('finance.read','accounting.read'):
            BusinessFoundation(self.office).save_grant(self.f.owner,dict(request_id=domain.rid(),user_id=user,permission=permission,effect='allow',scope='*',revision=0))
        token=self.login('finance@travel.example.test','Synthetic-finance-password-123')
        public=self.call('GET','/business/personnel/travel/financial/'+accepted['target_id']+'?revision=1',token=token).json
        self.assertEqual(public['cash_movements'][0]['amount'],'14.00')
        for secret in (self.f.employee['id'],self.f.employee['name'],self.f.file['id'],'Actual customer visit'):
            self.assertNotIn(secret,json.dumps(public))
        self.call('GET','/business/personnel/travel/payments?employee_id='+self.f.employee['id'],token=token,status=403)
    def test_http_strict_methods_query_body_and_dst_options(self):
        options=self.call('GET','/business/personnel/travel/time-options?local=2026-10-25T02:30&timezone=Europe%2FBerlin',token=self.tech).json
        self.assertEqual(len(options['options']),2)
        self.call('GET','/business/personnel/travel/catalog',{'extra':True},status=400)
        self.call('GET','/business/personnel/travel/catalog?extra=1',status=400)
        self.call('POST','/business/personnel/travel/catalog',{},status=405)
        self.call('POST','/business/personnel/travel/trips?extra=1',self.f.trip_body(),token=self.tech,status=400)
        self.call('GET','/business/personnel/travel/trips/'+domain.rid()+'?revision=abc',status=400)
        duplicate=json.dumps(self.f.trip_body())[:-1]+',"revision":0}'
        response=self.client.post('/api/v1/business/personnel/travel/trips',base_url='https://travel.example.test',data=duplicate,
            content_type='application/json',headers={'Authorization':'Bearer '+self.tech})
        self.assertEqual(response.status_code,400)
        malformed=self.f.trip_body();malformed['details']['source_file_ids']=[{}]
        self.call('POST','/business/personnel/travel/trips',malformed,token=self.tech,status=400)
        malformed=self.f.trip_body();malformed['details']['private_intervals']=[{}]
        self.call('POST','/business/personnel/travel/trips',malformed,token=self.tech,status=400)
        malformed=self.f.trip_body();malformed['details']['transport_facts']=[dict(kind='flight',legs='invalid',source_file_ids=[self.f.file['id']])]
        self.call('POST','/business/personnel/travel/trips',malformed,token=self.tech,status=400)

    def test_archived_json_download_preserves_original_bytes_hash_and_filename(self):
        settlement=self.f.api.approve(self.f.owner,self.f.approval(self.f.submitted()))['result']
        expected,mime=self.f.api.export(self.f.owner,settlement['id'],1,'json')
        response=self.call('GET','/business/personnel/travel/settlements/'+settlement['id']+'/export?format=json&revision=1')
        metadata=settlement['exports']['json']
        self.assertEqual(response.data,expected)
        self.assertEqual(response.mimetype,mime)
        self.assertEqual(len(response.data),metadata['size'])
        self.assertEqual(hashlib.sha256(response.data).hexdigest(),metadata['sha256'])
        self.assertIn(metadata['filename'],response.headers['Content-Disposition'])
        self.assertNotIn('exports',response.json)

