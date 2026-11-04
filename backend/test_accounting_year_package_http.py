"""Actual local HTTP and actual MFA routes for immutable year ZIP downloads."""
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
import unittest

import test_accounting_year_package as fixture
from accounting_year_verify_v1 import verify
from onedrive import OneDrive
from server import make_handler
from online.auth import totp
from online.storage import Storage
from online.test_instance_isolation import MFA_SCHEMA
from online.web import create_app


class YearPackageHTTP(unittest.TestCase):
    def setUp(self):
        self.f=fixture.YearPackageTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.office=self.f.office;self.export,unused,unused2=self.f.year()
        self.path='/business/accounting/euer/exports/'+self.export['id']+'/evidence'
        self.email='year-http-owner@example.test';self.password='Synthetic-local-only-year-password-123'
        self.user=self.office.add_user(self.email,self.password,'owner')

    def test_actual_loopback_binary_hash_strict_requests_and_fresh_revocation(self):
        token=self.office.login(self.email,self.password)
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.office,OneDrive(self.office)))
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        self.addCleanup(worker.join);self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        def call(suffix='',method='GET',body=None):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=15)
            try:
                connection.request(method,'/api'+self.path+suffix,body=body,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
                response=connection.getresponse();return response.status,dict(response.headers),response.read()
            finally:connection.close()
        status,headers,body=call();self.assertEqual(status,200);metadata=json.loads(body)
        status,headers,raw=call('/archive');self.assertEqual(status,200);self.assertEqual(headers['Content-Type'],'application/zip')
        self.assertEqual(headers['Cache-Control'],'no-store');self.assertIn(metadata['filename'],headers['Content-Disposition'])
        self.assertEqual(len(raw),metadata['size']);self.assertTrue(verify(raw,metadata['sha256'])['verified'])
        self.assertEqual(call('/archive')[2],raw)
        for args in [('?extra=1','GET',None),('','GET',b'{}'),('','POST',b'{}')]:
            self.assertIn(call(*args)[0],(400,405))
        with self.office.db:self.office.db.execute("UPDATE users SET active=0 WHERE id=?",(self.user,))
        self.assertIn(call('/archive')[0],(401,403))

    def test_actual_mfa_metadata_download_and_foreign_export(self):
        self.office.db.executescript(MFA_SCHEMA)
        host='year-review.example.test';storage=Storage(self.office,self.f.key,host,config={'server':{'path':str(Path(self.f.temp.name)/'company')}})
        client=create_app(office=self.office,key=self.f.key,host=host,instance_id=self.f.instance,storage=storage).test_client()
        base='https://'+host
        first=client.post('/api/v1/login',base_url=base,json={'email':self.email,'password':self.password})
        self.assertEqual(first.status_code,200);pending=first.json;self.assertNotIn('token',pending)
        verified=client.post('/api/v1/login/verify',base_url=base,json={'challenge':pending['challenge'],'code':totp(pending['enrollment']['secret'],int(time.time()//30))})
        self.assertEqual(verified.status_code,200);headers={'Authorization':'Bearer '+verified.json['token']}
        metadata=client.get('/api/v1'+self.path,base_url=base,headers=headers)
        self.assertEqual(metadata.status_code,200)
        archive=client.get('/api/v1'+self.path+'/archive',base_url=base,headers=headers)
        self.assertEqual(archive.status_code,200);self.assertEqual(archive.mimetype,'application/zip')
        self.assertEqual(archive.headers['Cache-Control'],'no-store');self.assertTrue(verify(archive.data,metadata.json['sha256'])['verified'])
        wrong=client.get('/api/v1'+self.path.replace(self.export['id'],'0'*32),base_url=base,headers=headers)
        self.assertEqual(wrong.status_code,404)
        malformed=client.get('/api/v1'+self.path+'?year=2026&year=2027',base_url=base,headers=headers)
        self.assertEqual(malformed.status_code,400)


if __name__=='__main__':unittest.main()
