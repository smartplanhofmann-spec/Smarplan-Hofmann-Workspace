"""Actual Flask/auth/SQL business operations; synthetic sources, no providers."""
import base64
import hashlib
import unittest
import uuid

import test_plan_imports as import_fixture


class OperationsHttpTests(unittest.TestCase):
    setUp=import_fixture.PlanImportApiTests.setUp
    tearDown=import_fixture.PlanImportApiTests.tearDown
    open_app=import_fixture.PlanImportApiTests.open_app
    call=import_fixture.PlanImportApiTests.call

    def req(self,**data): return dict(request_id=uuid.uuid4().hex,**data)

    def test_authenticated_photo_resume_annotation_and_exact_original_download(self):
        content=import_fixture.png()
        media=self.call('POST','/business/media',self.req(project_id=self.project,filename='synthetic.png',media_type='image/png',size=len(content),sha256=hashlib.sha256(content).hexdigest()),status=201).json
        path='/business/media/'+media['id']
        self.call('GET',path+'/content',status=409)
        chunk={'content_base64':base64.b64encode(content).decode()}
        self.call('POST',path+'/chunks/0',chunk)
        self.call('POST',path+'/chunks/0',chunk)
        completed=self.call('POST',path+'/complete',self.req()).json
        updated=self.call('POST',path,self.req(revision=completed['revision'],caption='Measured on site',annotations=[{'kind':'line','points':[[0.1,0.1],[0.8,0.1]]}])).json
        self.assertEqual(updated['caption'],'Measured on site')
        self.assertEqual(self.call('GET',path+'/content').data,content)
        self.assertEqual(self.call('GET','/business/media?project_id='+self.project).json['items'],[updated])
        self.call('GET',path,token=None,status=401)
        self.call('POST',path+'/chunks/0',{'content_base64':'not valid base64'},status=400)
        self.assertEqual(self.call('GET',path+'/content').data,content)

    def test_measurement_signature_artifact_and_same_project_service_visit_flow(self):
        measurement=self.call('POST','/business/measurements',self.req(project_id=self.project,title='Synthetic room',lines=[
            {'description':'Floor','unit':'m2','formula':'length * width','variables':{'length':{'value':'3','unit':'m'},'width':{'value':'2','unit':'m'}}}]),status=201).json
        path='/business/measurements/'+measurement['id']
        signed=self.call('POST',path+'/sign',self.req(revision=1,expected_hash=measurement['content_hash'],signer='Synthetic customer',strokes=[[[0.1,0.2],[0.8,0.6]]])).json
        artifact=self.call('GET',path+'/pdf')
        self.assertTrue(artifact.data.startswith(b'%PDF-'))
        self.assertEqual(hashlib.sha256(artifact.data).hexdigest(),signed['pdf_sha256'])
        self.call('POST',path,self.req(revision=2,title='Cannot overwrite'),status=409)
        asset=self.call('POST','/business/assets',self.req(project_id=self.project,name='Synthetic panel',serial_number='SYN-123'),status=201).json
        contract=self.call('POST','/business/maintenance/contracts',self.req(project_id=self.project,asset_id=asset['id'],title='Synthetic visit',anchor_date='2026-10-01',interval_unit='months',interval_count=12),status=201).json
        visit=self.call('POST','/business/maintenance/schedule',self.req(project_id=self.project,as_of='2026-10-01')).json['items'][0]
        checklist=self.call('POST','/business/checklists',self.req(project_id=self.project,title='Checks',items=[{'key':'safe','label':'Safe','required':True,'type':'boolean'}]),status=201).json
        run=self.call('POST','/business/checklists/'+checklist['id']+'/start',self.req()).json
        self.call('POST','/business/checklists/'+run['id']+'/answers',self.req(revision=1,answers={'safe':True}))
        report=self.call('POST','/business/checklists/'+run['id']+'/report',self.req()).json
        self.assertEqual(report['checklist']['answers'],{'safe':True})
        self.call('POST','/business/service-reports/'+report['id']+'/sign',self.req(revision=1,expected_hash=report['content_hash'],signer='Synthetic customer',strokes=[[[0,0],[1,1]]]))
        completed=self.call('POST','/business/maintenance/visits/'+visit['id']+'/complete',self.req(revision=1,report_id=report['id'])).json
        self.assertEqual((completed['status'],completed['contract_id']),('completed',contract['id']))
        self.assertEqual(self.call('GET','/business/maintenance/history?project_id='+self.project).json['items'][0],completed)

    def test_real_stock_reservation_pick_and_costs_over_http(self):
        article=self.call('POST','/business/articles',self.req(code='SYN-STOCK',name='Synthetic cable',kind='material',unit='m',unit_price_net='3',cost_price_net='1.25',tax_rate='19',tax_category='S',currency='EUR',active=True)).json
        location=self.call('POST','/business/inventory/locations',self.req(name='Synthetic store'),status=201).json
        self.call('POST','/business/inventory/movements',self.req(kind='receive',article_id=article['id'],to_location_id=location['id'],quantity='10',unit_cost_net='1.25'),status=201)
        reservation=self.call('POST','/business/inventory/reservations',self.req(project_id=self.project,article_id=article['id'],location_id=location['id'],quantity='4'),status=201).json
        body=self.req(project_id=self.project,items=[{'reservation_id':reservation['id'],'quantity':'2'}])
        first=self.call('POST','/business/inventory/pick',body).json
        self.assertEqual(self.call('POST','/business/inventory/pick',body).json,first)
        stock=self.call('GET','/business/inventory/stock?location_id='+location['id']+'&article_id='+article['id']).json
        self.assertEqual((stock['on_hand'],stock['reserved'],stock['available']),('8.0000','2.0000','6.0000'))
        self.assertEqual(self.call('GET','/business/projects/'+self.project+'/costs').json['material_actual_net'],'2.50')
        change=self.call('POST','/business/projects/'+self.project+'/changes',self.req(title='Synthetic change',amount_net='10.00',approved=False),status=201).json
        approval=self.req(revision=change['revision'])
        approved=self.call('POST','/business/projects/'+self.project+'/changes/'+change['id']+'/approve',approval).json
        self.assertEqual(self.call('POST','/business/projects/'+self.project+'/changes/'+change['id']+'/approve',approval).json,approved)
        self.assertEqual(self.call('GET','/business/projects/'+self.project+'/costs').json['approved_changes_net'],'10.00')
        self.call('GET','/business/inventory/pick',status=405)

if __name__=='__main__': unittest.main()
