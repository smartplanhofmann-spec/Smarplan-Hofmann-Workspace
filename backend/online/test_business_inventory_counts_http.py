"""Authenticated count, cost, source conflict and historical replay HTTP checks."""
import unittest

from core import Office
import business_schema
from online import test_purchasing_journey as fixture


class InventoryCountHttpTests(unittest.TestCase):
    def setUp(self):
        fixture.PurchasingJourneyTests.setUp(self)
        self.call('/users',dict(email='counter@example.test',password='Synthetic-counter-password-123',role='technician'),status=201)
        self.tech_token=self.login('counter@example.test','Synthetic-counter-password-123')
    open_app=fixture.PurchasingJourneyTests.open_app
    call=fixture.PurchasingJourneyTests.call
    login=fixture.PurchasingJourneyTests.login
    article_record=fixture.PurchasingJourneyTests.article_record

    def workflow(self):
        location=self.location['id']; article=self.article['id']
        self.call('/business/inventory/movements',fixture.request(kind='receive',article_id=article,to_location_id=location,quantity='10',unit_cost_net='2.1250'),status=201)
        create=fixture.request(location_id=location,article_ids=[article],title='Synthetic count',counted_on='2026-11-03',correction_of=None,reason='Physical count')
        opened=self.call('/business/inventory/counts',create,status=201).json
        count=fixture.request(revision=1,lines=[dict(article_id=article,quantity='8',reason='Two damaged units')])
        counted=self.call('/business/inventory/counts/'+opened['id']+'/count',count).json
        self.assertEqual(counted['items'][0]['difference'],'-2.0000')
        command=fixture.request(revision=2,confirmed=True,zero_stock_unit_costs={})
        path='/business/inventory/counts/'+opened['id']
        self.call(path+'/approve',command,token=self.tech_token,status=403)
        self.assertEqual(self.call(path+'?revision=1').json['status'],'open')
        result=self.call(path+'/approve',command).json
        self.assertEqual(result['items'][0]['adjustment_value_net'],'-4.2500')
        self.assertEqual(self.call(path+'/approve',command).json,result)
        self.assertEqual(self.call('/business/inventory/stock?location_id='+location+'&article_id='+article).json['on_hand'],'8.0000')
        issue=self.call('/business/inventory/movements',fixture.request(kind='issue',article_id=article,from_location_id=location,project_id=self.project,quantity='3'),status=201).json
        self.assertEqual(issue['cost_net'],'6.3750')
        self.assertEqual(self.call(path+'/approve',command).json,result)
        self.call(path+'?ignored=1',status=400)
        self.call(path+'/approve?ignored=1',command,status=400)
        self.call('/business/inventory/counts/'+opened['id'],{},method='GET',status=400)
        operational=self.call(path,token=self.tech_token).json
        self.assertFalse(operational['financial_values_visible'])
        self.assertNotIn('value_net',operational['items'][0])
        self.assertNotIn('adjustment_value_net',operational['items'][0])
        self.assertTrue(business_schema.validate_integrity(self.office))
        return command,result

    def test_actual_http_restart_and_historical_count(self):
        command,result=self.workflow()
        self.office.db.close();self.office=Office(self.database);self.open_app()
        self.assertEqual(self.call('/business/inventory/counts/'+result['id']+'/approve',command).json,result)
        self.assertEqual(len(self.call('/business/inventory/counts/'+result['id']+'/history').json['items']),3)


if __name__=='__main__':unittest.main()
