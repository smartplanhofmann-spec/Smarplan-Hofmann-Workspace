"""Read-only original report receipts; no old text or signature is uploaded."""
from copy import deepcopy
import hashlib
import json
import os
import unittest
import uuid
import struct
from datetime import datetime,timedelta,timezone

from core import canonical, digest
from online import test_offline_instance_binding as instances
from business_offline_reports import ACTION

PATH='/business/offline/recovery/service-report'

def reference_hash(value):
    def typed(v):
        if isinstance(v,float):return {'$float64':struct.pack('>d',v).hex()}
        if isinstance(v,list):return [typed(item) for item in v]
        if isinstance(v,dict):return {key:typed(item) for key,item in v.items()}
        return v
    return digest(canonical(typed(value)))


def capture_body(office,actor,project_id):
    project=office.project(actor,project_id);now=datetime.now(timezone.utc).replace(microsecond=0)
    content=dict(title=' Synthetischer Altbericht ä ',description='Originale Leistung.\nNichts verändert.',notes='',
        project_name=project['name'],customer=project['customer'],captured_at=(now-timedelta(minutes=10)).isoformat())
    entry=uuid.uuid4().hex
    return dict(request_id=uuid.uuid4().hex,entry_id=entry,project_id=project_id,content=content,
        content_hash=digest(canonical([entry,project_id,content])),signer=' Synthetischer Kunde ',
        strokes=[[[0.1,0.2],[0.8,0.7]]],signed_at=(now-timedelta(minutes=5)).isoformat())



class LegacyServiceReportRecoveryHttpTests(unittest.TestCase):
    def setUp(self):
        self.f=instances.OfflineInstanceBindingHttpTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.company=self.f.a;self.owner=self.company['office'].user(self.company['token'])
        self.body=capture_body(self.company['office'],self.owner,self.f.project)
        self.accepted=self.f.call(self.company,'/business/service-reports/offline',self.body,status=201).json
        old={k:v for k,v in self.body.items() if k!='project_id'}
        self.request=dict(schema_version=4,nonce=uuid.uuid4().hex,kind='service_report_capture',
            project_id=self.f.project,entry_id=self.body['entry_id'],request_id=self.body['request_id'],
            capture_hash=reference_hash([ACTION,self.f.project,self.body['entry_id'],old]))

    def call(self,body=None,*,company=None,status=200,**kw):
        return self.f.call(company or self.company,PATH,body or self.request,status=status,**kw)

    def test_actual_mfa_original_signature_and_pdf_are_confirmed_without_new_record_or_payload(self):
        self.assertIn('offline_service_report_recovery',self.f.call(self.company,'/business/capabilities').json['features'])
        tables=('business_operation_entries','business_operation_versions','business_operations_requests','audit')
        db=self.company['office'].db
        before={t:[dict(v) for v in db.execute('SELECT * FROM '+t)] for t in tables}
        response=self.call();proof=response.json
        self.assertEqual(proof['schema_version'],4);self.assertEqual(proof['nonce'],self.request['nonce'])
        self.assertEqual(proof['lookup_hash'],digest(canonical(self.request)))
        self.assertEqual(proof['binding']['instance_id'],self.company['instance_id'])
        original=proof['original']
        self.assertEqual(original['capture_hash'],self.request['capture_hash'])
        self.assertEqual(original['request_hash'],self.accepted['offline_capture']['request_hash'])
        self.assertEqual(original['actor_id'],self.owner['id'])
        self.assertEqual(original['pdf_sha256'],self.accepted['pdf_sha256'])
        self.assertEqual(original['signature_sha256'],reference_hash({k:self.body[k] for k in ('content_hash','signer','strokes','signed_at')}))
        for key in ('content','strokes','signer','title','description','notes','customer','project_name'):
            self.assertNotIn(key,original)
        self.assertIn('no-store',response.headers['Cache-Control'])
        self.assertEqual({t:[dict(v) for v in db.execute('SELECT * FROM '+t)] for t in tables},before)
        self.assertEqual(self.call().json,proof)

    def test_same_account_and_project_in_another_company_do_not_receive_missing_original(self):
        value=self.call(company=self.f.b,status=404).json
        self.assertNotIn('original',value)
        self.assertEqual(self.f.b['office'].db.execute('SELECT COUNT(*) FROM business_operation_entries').fetchone()[0],0)

    def test_unknown_receipt_or_changed_hash_and_uploaded_content_are_never_treated_as_success(self):
        for change,status in (({'request_id':uuid.uuid4().hex},404),({'entry_id':uuid.uuid4().hex},409),
                ({'capture_hash':'0'*64},409),({'content':self.body['content']},400),
                ({'strokes':self.body['strokes']},400),({'schema_version':True},400)):
            with self.subTest(change=list(change)):
                value=self.call(dict(self.request,**change),status=status).json
                self.assertNotIn('original',value)

    def test_recovery_stays_read_only_when_documents_are_paused(self):
        state=self.f.call(self.company,'/business/organization').json
        modules={k:dict(visible=v['visibility_override'],enabled=v['enabled']) for k,v in state['modules'].items()}
        modules['documents']['enabled']=False
        self.f.call(self.company,'/business/organization',dict(request_id=uuid.uuid4().hex,
            revision=state['revision'],needs=state['needs'],modules=modules))
        self.assertEqual(self.call().json['original']['pdf_sha256'],self.accepted['pdf_sha256'])
        self.assertEqual(self.company['office'].db.execute('SELECT COUNT(*) FROM business_operation_entries').fetchone()[0],1)

    def test_exact_coordinate_bits_preserve_negative_zero_fraction_and_exponent(self):
        body=capture_body(self.company['office'],self.owner,self.f.project)
        body['strokes']=[[[0.0,-0.0],[1e-7,0.1],[1,1.0]]]
        accepted=self.f.call(self.company,'/business/service-reports/offline',body,status=201).json
        old={k:v for k,v in body.items() if k!='project_id'}
        query=dict(self.request,entry_id=body['entry_id'],request_id=body['request_id'],
            capture_hash=reference_hash([ACTION,self.f.project,body['entry_id'],old]))
        self.assertEqual(self.call(query).json['original']['pdf_sha256'],accepted['pdf_sha256'])
        changed=deepcopy(old);changed['strokes'][0][0][1]=0.0
        self.call(dict(query,capture_hash=reference_hash([ACTION,self.f.project,body['entry_id'],changed])),status=409)

    def test_return_mode_retains_read_proof_without_releasing_document_writes(self):
        from business_schema import set_mode
        proof=self.call().json
        set_mode(self.company['office'],'legacy')
        self.assertEqual(self.call().json,proof)
        self.f.call(self.company,'/business/service-reports/offline',self.body,status=409)

    def test_device_tokens_and_inactive_identity_cannot_read_private_original(self):
        for route in ('/offline/access/v2','/business/offline/access/v2'):
            grant=self.f.call(self.company,route,{},status=201).json
            self.f.call(self.company,PATH,self.request,token=grant['token'],status=403,
                headers={'X-Smartplan-Offline-Binding':self.company['instance_id']+':'+self.owner['id']})
        with self.company['office'].db:
            self.company['office'].db.execute('UPDATE users SET active=0 WHERE id=?',(self.owner['id'],))
        self.call(status=401)

    def test_raw_json_limit_duplicate_fields_media_method_and_query_are_strict(self):
        self.f.call(self.company,PATH+'?project_id='+self.f.project,self.request,status=400)
        self.f.call(self.company,PATH,method='GET',status=405)
        raw=json.dumps(self.request).encode()
        headers={'Authorization':'Bearer '+self.company['token']}
        for data,media,status in ((raw[:-1]+b',"schema_version":4}', 'application/json',400),
                (raw+b' '*4096,'application/json',413),(raw,'text/plain',415)):
            with self.subTest(status=status):
                response=self.company['client'].post('/api/v1'+PATH,base_url='https://same.example.test',
                    headers=headers,data=data,content_type=media)
                self.assertEqual(response.status_code,status)

    def test_own_archive_and_fresh_project_assignment_are_required_for_a_technician(self):
        office=self.company['office']
        user=office.add_user('retained-report-worker@example.test',instances.PASSWORD,'technician')
        self.f.call(self.company,'/assignments',dict(project_id=self.f.project,user_id=user))
        token=self.f.login(self.company,'retained-report-worker@example.test')
        self.call(token=token,status=404)
        body=capture_body(office,office.user(token),self.f.project)
        accepted=self.f.call(self.company,'/business/service-reports/offline',body,token=token,status=201).json
        old={k:v for k,v in body.items() if k!='project_id'}
        query=dict(self.request,entry_id=body['entry_id'],request_id=body['request_id'],
            capture_hash=reference_hash([ACTION,self.f.project,body['entry_id'],old]))
        self.assertEqual(self.call(query,token=token).json['original']['pdf_sha256'],accepted['pdf_sha256'])
        self.f.call(self.company,'/assignments',dict(project_id=self.f.project,user_id=user,remove=True))
        self.call(query,token=token,status=404)


@unittest.skipUnless(os.name=='posix','Private POSIX local runtime required')
class LegacyServiceReportRecoveryLocalTests(unittest.TestCase):
    def setUp(self):
        self.f=instances.OfflineInstanceBindingLocalHttpTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.body=capture_body(self.f.office,self.f.office.user(self.f.full),self.f.project)
        self.accepted=self.f.call('/business/service-reports/offline',self.body,status=201)
        old={k:v for k,v in self.body.items() if k!='project_id'}
        self.query=dict(schema_version=4,nonce=uuid.uuid4().hex,kind='service_report_capture',
            project_id=self.f.project,entry_id=self.body['entry_id'],request_id=self.body['request_id'],
            capture_hash=reference_hash([ACTION,self.f.project,self.body['entry_id'],old]))

    def test_actual_local_server_proves_original_signature_without_consuming_or_replaying_capture(self):
        before=[dict(v) for v in self.f.office.db.execute('SELECT * FROM business_operations_requests')]
        proof=self.f.call(PATH,self.query)
        self.assertEqual(proof['original']['pdf_sha256'],self.accepted['pdf_sha256'])
        self.assertEqual(proof['binding']['instance_id'],self.f.instance)
        self.assertEqual([dict(v) for v in self.f.office.db.execute('SELECT * FROM business_operations_requests')],before)

    def test_local_server_preserves_raw_framing_query_and_body_limit(self):
        from http.client import HTTPConnection
        self.f.call(PATH+'?extra=1',self.query,status=400)
        self.f.call(PATH,status=405)
        raw=json.dumps(self.query).encode()
        for data,status in ((raw[:-1]+b',"schema_version":4}',400),(raw+b' '*4096,413)):
            connection=HTTPConnection('127.0.0.1',self.f.server.server_port,timeout=6)
            try:
                connection.request('POST','/api'+PATH,body=data,
                    headers={'Authorization':'Bearer '+self.f.full,'Content-Type':'application/json'})
                response=connection.getresponse();response.read();self.assertEqual(response.status,status)
            finally:connection.close()


if __name__=='__main__':unittest.main()
