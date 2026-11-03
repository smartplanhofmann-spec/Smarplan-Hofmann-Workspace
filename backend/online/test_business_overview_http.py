"""Actual MFA HTTP overview, canonical sources, framing and restart checks."""
import unittest
from core import Office
from online import test_purchasing_journey as fixture


class OverviewHttpTests(unittest.TestCase):
    setUp = fixture.PurchasingJourneyTests.setUp
    open_app = fixture.PurchasingJourneyTests.open_app
    call = fixture.PurchasingJourneyTests.call
    login = fixture.PurchasingJourneyTests.login
    article_record = fixture.PurchasingJourneyTests.article_record

    def test_mfa_sources_restart_and_strict_read_contract(self):
        task = self.call('/projects/'+self.project+'/tasks', fixture.request(
            title='Synthetic overview task', due_date='2026-01-01'), status=201).json
        value = self.call('/business/overview/metrics').json
        source = next(item for item in value['tasks'] if item['id'] == task['id'])
        self.assertEqual(self.call(source['source_path']).json['id'], task['id'])
        self.assertEqual(1, value['task_count'])
        self.assertEqual('0.00', value['finance']['revenue_net'])
        self.assertIsNone(value['accounting']['balance'])
        self.call('/business/overview/metrics', token=None, status=401)
        self.call('/business/overview/metrics?project_id='+self.project+'&project_id='+self.project, status=400)
        self.call('/business/overview/metrics?unknown=true', status=400)
        self.call('/business/overview/metrics', {}, method='GET', status=400)
        self.call('/business/overview/metrics', {}, status=405)
        self.office.db.close(); self.office = Office(self.database); self.open_app()
        again = self.call('/business/overview/metrics').json
        self.assertEqual(value['source_hash'], again['source_hash'])
        self.assertEqual(value['finance'], again['finance'])


if __name__ == '__main__': unittest.main()
