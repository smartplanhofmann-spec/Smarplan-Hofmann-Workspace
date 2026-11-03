"""Real loopback HTTP framing and exact large original transfers, local storage."""
import base64
import http.client
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest

from core import Office
from onedrive import OneDrive
from server import make_handler
from business_purchase_changes import MAX_FILE
from test_business_resource_custody import req


class PurchaseChangesLocalHTTP(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='synthetic-purchase-change-http-');self.addCleanup(temporary.cleanup)
        self.office=Office(Path(temporary.name)/'office.db');self.addCleanup(self.office.db.close)
        self.office.add_user('purchase-local@example.test','Synthetic-local-purchase-password','owner')
        self.token=self.office.login('purchase-local@example.test','Synthetic-local-purchase-password')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.office,OneDrive(self.office)))
        worker=threading.Thread(target=self.server.serve_forever,daemon=True);worker.start()
        self.addCleanup(worker.join);self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        from business_documents import Documents
        from business_inventory import BusinessInventory
        actor=self.office.user(self.token)
        article=Documents(self.office).save_article(actor,req(code='SYN-HTTP',name='Synthetic actual material',kind='material',unit='C62',unit_price_net='10',cost_price_net='5',tax_rate='19',tax_category='S',currency='EUR',active=True))
        order=BusinessInventory(self.office).save_order(actor,req(project_id=None,supplier_name='Synthetic supplier',status='approved',items=[dict(article_id=article['id'],quantity='3')]))
        self.path='/api/business/purchasing/orders/'+order['id']

    def call(self,method,path,body=None,status=200,headers=None):
        connection=http.client.HTTPConnection('127.0.0.1',self.server.server_port,timeout=10)
        try:
            encoded=json.dumps(body).encode() if body is not None else None
            connection.request(method,path,encoded,dict({'Authorization':'Bearer '+self.token,'Content-Type':'application/json'},**(headers or {})))
            response=connection.getresponse();raw=response.read();self.assertEqual(response.status,status,raw[:300])
            return json.loads(raw) if response.getheader('Content-Type','').startswith('application/json') else raw
        finally:connection.close()
    def test_maximum_two_mib_original_is_downloaded_byte_exact_and_replayed_without_duplicate(self):
        raw=b'%PDF-1.7\n'+b'x'*(MAX_FILE-9)
        self.assertEqual(len(raw),MAX_FILE)
        body=req(filename='max-original.pdf',media_type='application/pdf',content_base64=base64.b64encode(raw).decode())
        result=self.call('POST',self.path+'/change-files',body)
        self.assertEqual(self.call('POST',self.path+'/change-files',body),result)
        self.assertEqual(self.call('GET',self.path+'/change-files/'+result['id']+'/original'),raw)
        self.assertEqual(len(self.call('GET',self.path+'/changes')['files']),1)
    def test_decoded_size_transport_size_other_routes_and_strict_framing(self):
        self.call('POST',self.path+'/change-files',req(filename='oversize.pdf',media_type='application/pdf',content_base64=base64.b64encode(b'x'*(MAX_FILE+1)).decode()),413)
        self.call('POST',self.path+'/change-files',{},413,headers={'Content-Length':'2850001'})
        self.call('POST','/api/business/resources',{},413,headers={'Content-Length':'1000001'})
        self.call('GET',self.path+'/changes',{},400)
        self.call('POST',self.path+'/change-files?ignored=1',{},400)
        self.call('GET',self.path+'/changes?ignored=1',status=400)
        self.assertEqual(self.call('GET',self.path+'/changes')['files'],[])


if __name__=='__main__':unittest.main()
