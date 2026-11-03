"""Real authenticated HTTP delivery, original, asset, service and restart path."""
import base64
import hashlib
import io
import unittest

from PIL import Image

from core import Office
from online import test_purchasing_journey as fixture
from business_asset_provenance import validate_integrity


class AssetDeliveryHttpTests(unittest.TestCase):
    setUp = fixture.PurchasingJourneyTests.setUp
    open_app = fixture.PurchasingJourneyTests.open_app
    call = fixture.PurchasingJourneyTests.call
    login = fixture.PurchasingJourneyTests.login
    article_record = fixture.PurchasingJourneyTests.article_record
    order = fixture.PurchasingJourneyTests.order
    receipt_body = fixture.PurchasingJourneyTests.receipt_body
    stock = fixture.PurchasingJourneyTests.stock
    costs = fixture.PurchasingJourneyTests.costs

    def create_chain(self):
        order = self.order()
        receipt = self.call('/business/purchasing/orders/'+order['id']+'/receipts',self.receipt_body(order),status=201).json
        issue = self.call('/business/inventory/movements',fixture.request(kind='issue',article_id=self.article['id'],
            from_location_id=self.location['id'],project_id=self.project,quantity='1'),status=201).json
        png=io.BytesIO();Image.new('RGB',(8,8),'#abcabc').save(png,format='PNG');original=png.getvalue()
        media=self.call('/business/media',fixture.request(project_id=self.project,filename='Original-Lieferschein.png',
            media_type='image/png',size=len(original),sha256=hashlib.sha256(original).hexdigest(),purpose='document',classification='operational'),status=201).json
        self.call('/business/media/'+media['id']+'/chunks/0',{'content_base64':base64.b64encode(original).decode()})
        self.call('/business/media/'+media['id']+'/complete',fixture.request())
        docpath='/business/purchasing/receipts/'+receipt['id']+'/document'
        body=fixture.request(media_id=media['id'],confirmed=True)
        document=self.call(docpath,body,status=201).json
        self.assertEqual(self.call(docpath,body,status=201).json,document)
        rows=self.call('/business/assets/origin-sources?project_id='+self.project).json['items']
        self.assertEqual(rows[0]['issues'][0]['id'],issue['id'])
        self.assertTrue(rows[0]['document_accessible'])
        command=fixture.request(project_id=self.project,asset={'name':'Installiertes Testgerät','serial_number':'HTTP-SYN-1'},
            receipt_id=receipt['id'],line_index=0,issue_movement_id=issue['id'],quantity='1',confirmed=True)
        before=self.costs()
        result=self.call('/business/assets/from-delivery',command,status=201).json
        self.assertEqual(self.call('/business/assets/from-delivery',command,status=201).json,result)
        self.assertEqual(self.costs(),before)
        originpath='/business/assets/'+result['id']+'/origin'
        self.assertEqual(self.call(originpath).json,result['origin'])
        self.assertEqual(self.call('/business'+document['download_path']).data,original)
        contract=self.call('/business/maintenance/contracts',fixture.request(project_id=self.project,asset_id=result['id'],
            title='Jahreswartung',anchor_date='2026-11-03',interval_unit='months',interval_count=12),status=201).json
        visit=self.call('/business/maintenance/schedule',fixture.request(project_id=self.project,as_of='2026-11-03')).json['items'][0]
        report=self.call('/business/service-reports',fixture.request(project_id=self.project,title='Gerätewartung',description='Seriennummer und Funktion geprüft.'),status=201).json
        report=self.call('/business/service-reports/'+report['id']+'/sign',fixture.request(revision=1,
            expected_hash=report['content_hash'],signer='Synthetischer Kunde',strokes=[[[.1,.2],[.8,.5]]])).json
        completed=self.call('/business/maintenance/visits/'+visit['id']+'/complete',fixture.request(revision=1,report_id=report['id'])).json
        self.assertEqual(completed['contract_id'],contract['id'])
        pdf=self.call('/business/service-reports/'+report['id']+'/pdf').data
        self.assertTrue(validate_integrity(self.office))
        return command, result, document, original, report, pdf, completed

    def test_original_delivery_asset_service_and_repeat_survive_http_restart(self):
        command, result, document, original, report, pdf, completed = self.create_chain()
        originpath='/business/assets/'+result['id']+'/origin'
        self.office.db.close();self.office=Office(self.database);self.open_app()
        self.assertEqual(self.call('/business/assets/from-delivery',command,status=201).json,result)
        self.assertEqual(self.call(originpath).json['document'],document)
        self.assertEqual(self.call('/business/service-reports/'+report['id']+'/pdf').data,pdf)
        self.assertEqual(self.call('/business/maintenance/history?project_id='+self.project+'&asset_id='+result['id']).json['items'][0],completed)
        self.call(originpath+'?ignored=1',status=400)
        self.call('/business/assets/from-delivery?ignored=1',command,status=400)


if __name__=='__main__':unittest.main()
