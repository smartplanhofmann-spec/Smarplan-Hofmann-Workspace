"""Actual authenticated transport for the isolated v2 source supplement."""
import http.client
from http.server import ThreadingHTTPServer
import json
import threading
import unittest
from onedrive import OneDrive
from server import make_handler
import test_accounting_year_package_v2 as fixture
from accounting_year_verify_v2 import verify

class YearPackageCarryoverHTTP(unittest.TestCase):
    def test_actual_v2_binary_metadata_and_current_user_access(self):
        f=fixture.YearPackageCarryover('runTest');f.setUp();self.addCleanup(f.doCleanups)
        _,_,export=f.complete();office=f.office
        user=office.add_user('v2-year@example.test','Synthetic-year-v2-local-password-123','owner')
        token=office.login('v2-year@example.test','Synthetic-year-v2-local-password-123')
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(office,OneDrive(office)))
        worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
        self.addCleanup(worker.join);self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        path='/api/business/accounting/euer/exports/'+export['id']+'/evidence'
        def get(suffix=''):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=15)
            try:
                connection.request('GET',path+suffix,headers={'Authorization':'Bearer '+token})
                response=connection.getresponse();return response.status,dict(response.headers),response.read()
            finally:connection.close()
        status,_,body=get();self.assertEqual(status,200);metadata=json.loads(body)
        self.assertEqual((metadata['format'],metadata['original_year_complete']),('smartplan-year-evidence-v2',True))
        status,headers,raw=get('/archive');self.assertEqual(status,200)
        self.assertEqual((headers['Content-Type'],headers['Cache-Control']),('application/zip','no-store'))
        self.assertTrue(verify(raw,metadata['sha256'])['verified']);self.assertEqual(len(raw),metadata['size'])
        self.assertEqual(get()[2],body);self.assertEqual(get('/archive')[2],raw)
        with office.db:office.db.execute('UPDATE users SET active=0 WHERE id=?',(user,))
        self.assertIn(get()[0],(401,403));self.assertIn(get('/archive')[0],(401,403))

if __name__=='__main__':unittest.main()
