"""HTTP need-to-know tests for legacy links and original Gmail files."""
import unittest
import uuid
from business_schema import set_mode
from core import canonical
import test_inquiry_attachments_api as af
import test_workspace_api as wf
import test_plan_imports as pf


def rid():return uuid.uuid4().hex


class ProjectDocumentAccessTests(af.AttachmentHttpFlow,unittest.TestCase):
    setUp=wf.WorkspaceApiTests.setUp
    tearDown=pf.PlanImportApiTests.tearDown
    open_app=pf.PlanImportApiTests.open_app

    def original(self):
        self.start_message()
        raw=af.synthetic_pdf()
        item=self.announce([self.descriptor(raw,media_type='application/pdf',filename='Synthetic protected original.pdf')])['files'][0]
        self.finish_file(item,raw)
        base=self.convert_message()
        return base,item,raw

    def classify(self,kind,identifier,value):
        path='/business/documents/'+kind+'/'+identifier+'/classification'
        current=self.call('GET',path).json
        return self.call('POST',path,{'request_id':rid(),'revision':current['revision'],
            'expected_source_fingerprint':current['source_fingerprint'],'classification':value}).json

    def test_unknown_mail_original_is_owner_only_then_owner_releases_exact_original(self):
        base,item,raw=self.original()
        _,tech=self.add_actor('technician')
        _,accountant=self.add_actor('accountant')
        path=base+'/mail-attachments'
        for token in (tech,accountant):
            body=self.call('GET',path,token=token).json
            self.assertEqual(body['files'],[])
            self.assertEqual((body['ready_count'],body['total_bytes']),(0,0))
            self.call('GET',path+'/'+item['id']+'/content',token=token,status=404)
        self.classify('mail',item['id'],'operational')
        self.assert_download(self.call('GET',path+'/'+item['id']+'/content',token=tech),raw,item['filename'])
        self.assertEqual(self.call('GET',path,token=tech).json['files'][0]['id'],item['id'])
        receipt=self.call('POST','/intake/gmail',self.envelope,token=self.connector['token'],status=201).json
        self.assertEqual(set(receipt),{'id','status','ingested_at'})
        self.assertEqual(receipt['id'],self.inquiry)

    def test_financial_original_is_never_shared_via_plan_copy_or_down_mode(self):
        base,item,_=self.original()
        _,tech=self.add_actor('technician')
        _,accountant=self.add_actor('accountant')
        self.classify('mail',item['id'],'financial')
        self.call('GET',base+'/mail-attachments/'+item['id']+'/content',token=tech,status=404)
        self.call('GET',base+'/mail-attachments/'+item['id']+'/content',token=accountant)
        self.call('POST',base+'/mail-attachments/'+item['id']+'/plan-import',{
            'request_id':rid(),'page':1,'title':'Cannot launder invoice as a plan'},status=403)
        set_mode(self.office,'legacy')
        self.call('GET',base+'/mail-attachments/'+item['id']+'/content',token=tech,status=404)
        self.call('GET',base+'/mail-attachments/'+item['id']+'/content',token=accountant)

    def test_link_url_revision_invalidates_release_and_cannot_replay_historical_url(self):
        _,tech=self.add_actor('technician')
        body={'request_id':rid(),'title':'Synthetic originally public link','url':'https://example.test/public',
              'category':'document','active':True}
        created=self.call('POST','/projects/'+self.project+'/links',body,token=tech,status=201).json
        self.classify('link',created['id'],'operational')
        self.call('GET','/projects/'+self.project+'/links/'+created['id'],token=tech)
        self.call('POST','/projects/'+self.project+'/links/'+created['id'],{
            'request_id':rid(),'revision':created['revision'],'url':'https://example.test/private-finance','category':'invoice'})
        self.call('POST','/projects/'+self.project+'/links',body,token=tech,status=404)
        self.assertEqual(self.call('GET','/projects/'+self.project+'/links',token=tech).json,[])

    def test_finance_read_does_not_allow_mutating_financial_link(self):
        uid,manager=self.add_actor('manager')
        self.call('POST','/business/settings/permissions',{'request_id':rid(),'revision':0,
            'user_id':uid,'permission':'finance.read','scope':self.project,'effect':'allow'})
        link=self.call('POST','/projects/'+self.project+'/links',{'request_id':rid(),'title':'Synthetic invoice',
            'url':'https://example.test/invoice','category':'invoice','active':True},status=201).json
        self.classify('link',link['id'],'financial')
        self.call('GET','/projects/'+self.project+'/links/'+link['id'],token=manager)
        self.call('POST','/projects/'+self.project+'/links/'+link['id'],{'request_id':rid(),
            'revision':link['revision'],'title':'Not authorized to change finance'},token=manager,status=403)

if __name__=='__main__':unittest.main()
