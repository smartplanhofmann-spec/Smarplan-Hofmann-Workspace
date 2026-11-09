"""Authenticated original-issue material returns, without external services."""
from decimal import Decimal
import unittest

import business_schema
from core import Office
from online import test_purchasing_journey as fixture


class MaterialReturnHttpTests(unittest.TestCase):
    setUp=fixture.PurchasingJourneyTests.setUp
    open_app=fixture.PurchasingJourneyTests.open_app
    call=fixture.PurchasingJourneyTests.call
    login=fixture.PurchasingJourneyTests.login
    article_record=fixture.PurchasingJourneyTests.article_record
    stock=fixture.PurchasingJourneyTests.stock
    costs=fixture.PurchasingJourneyTests.costs

    def initial_issue(self, *, quantity='6', receive='10', cost='10'):
        self.call('/business/inventory/movements',fixture.request(kind='receive',article_id=self.article['id'],
            to_location_id=self.location['id'],quantity=receive,unit_cost_net=cost),status=201)
        return self.call('/business/inventory/movements',fixture.request(kind='issue',article_id=self.article['id'],
            from_location_id=self.location['id'],project_id=self.project,quantity=quantity),status=201).json

    def return_body(self, issue, quantity):
        return fixture.request(kind='return',article_id=issue['article_id'],project_id=issue['project_id'],
            to_location_id=self.location['id'],quantity=quantity,reversal_of=issue['id'],note='Synthetic actual project return')

    def movement_rows(self):
        return [dict(row) for row in self.office.db.execute('SELECT * FROM business_stock_movements ORDER BY sequence_number')]

    def workflow(self):
        issue=self.initial_issue()
        before=self.movement_rows()
        self.assertEqual((self.stock()['on_hand'],self.costs()['material_actual_net']),('4.0000','60.00'))
        self.call('/business/articles/'+self.article['id'],fixture.request(revision=self.article['revision'],cost_price_net='99'))
        command=self.return_body(issue,'2')
        first=self.call('/business/inventory/movements',command,status=201).json
        self.assertEqual((first['unit_cost_net'],first['cost_net']),('10.0000','20.0000'))
        self.assertEqual((first['reversal_of'],first['article_id'],first['project_id']),
            (issue['id'],issue['article_id'],issue['project_id']))
        self.assertIsNone(first['from_location_id'])
        self.assertEqual((self.stock()['on_hand'],self.stock()['stock_value_net'],self.costs()['material_actual_net']),('6.0000','60.00','40.00'))
        self.assertEqual(self.call('/business/inventory/movements',command,status=201).json,first)
        self.assertEqual(self.call('/business/inventory/movements/'+issue['id']).json,issue)
        self.assertEqual(self.movement_rows()[:len(before)],before)
        self.call('/business/inventory/movements',dict(command,quantity='1'),status=409)
        before_invalid=self.movement_rows()
        other_article=self.article_record('SYN-OTHER-RETURN')
        other_project=self.call('/projects',{'name':'Synthetic other project','customer':'Synthetic other customer'},status=201).json['id']
        for body in [dict(self.return_body(issue,'1'),article_id=other_article['id']),
                     dict(self.return_body(issue,'1'),project_id=other_project),
                     dict(self.return_body(issue,'1'),unit_cost_net='99'),
                     dict(self.return_body(issue,'1'),from_location_id=self.location['id'])]:
            self.call('/business/inventory/movements',body,status=400)
        self.assertEqual(self.movement_rows(),before_invalid)
        second=self.call('/business/inventory/movements',self.return_body(issue,'1'),status=201).json
        self.assertEqual((second['cost_net'],self.stock()['on_hand'],self.costs()['material_actual_net']),('10.0000','7.0000','30.00'))
        before_invalid=self.movement_rows()
        self.call('/business/inventory/movements',self.return_body(issue,'4'),status=409)
        self.assertEqual(self.movement_rows(),before_invalid)
        final=self.call('/business/inventory/movements',self.return_body(issue,'3'),status=201).json
        self.assertEqual((self.stock()['on_hand'],self.costs()['material_actual_net']),('10.0000','0.00'))
        self.assertEqual(sum(Decimal(row['cost_net']) for row in (first,second,final)),Decimal(issue['cost_net']))
        self.call('/business/inventory/movements',self.return_body(issue,'0.0001'),status=409)
        self.assertEqual(self.call('/business/inventory/movements',command,status=201).json,first)
        self.assertEqual(self.call('/business/inventory/movements/'+issue['id']).json,issue)
        self.assertTrue(business_schema.validate_integrity(self.office))
        return command,first,issue

    def test_actual_http_partial_multiple_overreturn_and_restart_preserve_original_cost(self):
        command,first,issue=self.workflow()
        snapshots=self.movement_rows()
        self.office.db.close();self.office=Office(self.database);self.open_app()
        self.assertEqual(self.call('/business/inventory/movements',command,status=201).json,first)
        self.assertEqual(self.call('/business/inventory/movements/'+issue['id']).json,issue)
        self.assertEqual(self.movement_rows(),snapshots)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_final_return_carries_original_rounding_remainder(self):
        self.call('/business/inventory/movements',fixture.request(kind='receive',article_id=self.article['id'],to_location_id=self.location['id'],quantity='1',unit_cost_net='1'),status=201)
        self.call('/business/inventory/movements',fixture.request(kind='receive',article_id=self.article['id'],to_location_id=self.location['id'],quantity='2',unit_cost_net='0'),status=201)
        issue=self.call('/business/inventory/movements',fixture.request(kind='issue',article_id=self.article['id'],from_location_id=self.location['id'],project_id=self.project,quantity='3'),status=201).json
        returned=[self.call('/business/inventory/movements',self.return_body(issue,'1'),status=201).json for _ in range(3)]
        self.assertEqual([row['cost_net'] for row in returned],['0.3333','0.3333','0.3334'])
        self.assertEqual(self.stock()['stock_value_net'],'1.00')
        self.assertEqual(self.costs()['material_actual_net'],'0.00')
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_explicit_unaccepted_conflict_never_labels_an_accepted_nonce_collision(self):
        issue=self.initial_issue();before=self.movement_rows()
        refused=self.return_body(issue,'7')
        response=self.call('/business/inventory/movements',refused,status=409)
        self.assertEqual(response.json.get('request_resolution'),'not_accepted')
        self.assertEqual(self.movement_rows(),before)
        self.assertIsNone(self.office.db.execute(
            'SELECT 1 FROM business_inventory_requests WHERE request_id=?',
            (refused['request_id'],)).fetchone())
        command=self.return_body(issue,'2')
        accepted=self.call('/business/inventory/movements',command,status=201).json
        collision=self.call('/business/inventory/movements',dict(command,quantity='1'),status=409)
        self.assertNotIn('request_resolution',collision.json)
        self.assertEqual(self.call('/business/inventory/movements',command,status=201).json,accepted)
        self.assertEqual(len(self.movement_rows()),len(before)+1)

    def test_current_project_write_rights_and_price_redaction_apply_to_original_retry(self):
        user=self.call('/users',dict(email='return-operator@example.test',password='Synthetic-return-password-123',role='technician'),status=201).json['id']
        tech=self.login('return-operator@example.test','Synthetic-return-password-123')
        self.call('/assignments',dict(project_id=self.project,user_id=user))
        self.call('/business/settings/permissions',fixture.request(user_id=user,permission='inventory.write',scope='*',effect='allow',revision=0))
        issue=self.initial_issue()
        command=self.return_body(issue,'1')
        returned=self.call('/business/inventory/movements',command,token=tech,status=201).json
        self.assertNotIn('cost_net',returned);self.assertNotIn('unit_cost_net',returned)
        self.assertNotIn('cost_price_net',returned['article_snapshot'])
        self.assertEqual(self.call('/business/inventory/movements',command,token=tech,status=201).json,returned)
        snapshots=self.movement_rows()
        self.call('/business/settings/permissions',fixture.request(user_id=user,permission='inventory.write',scope='*',effect='deny',revision=1))
        self.call('/business/inventory/movements',command,token=tech,status=403)
        self.assertEqual(self.movement_rows(),snapshots)
        self.call('/business/settings/permissions',fixture.request(user_id=user,permission='inventory.write',scope='*',effect='allow',revision=2))
        self.call('/assignments',dict(project_id=self.project,user_id=user,remove=True))
        self.call('/business/inventory/movements',command,token=tech,status=404)
        self.assertEqual(self.movement_rows(),snapshots)
        self.assertTrue(business_schema.validate_integrity(self.office))


if __name__=='__main__':unittest.main()
