"""Synthetic, real immutable stock sources consumed by browser and native tests."""
from copy import deepcopy
from decimal import Decimal

import business_inventory
from business_documents import Documents
import test_business_inventory as inventory_fixture


class MaterialReturnFixture:
    def __init__(self, owner):
        self.f = f = inventory_fixture.InventoryTests('runTest')
        f.setUp()
        owner.addCleanup(f.doCleanups)

    def state(self):
        f = self.f
        return dict(stock=f.api.balance(f.owner, f.location['id'], f.article['id']),
                    costs=f.api.cost_report(f.owner, f.project),
                    movements=business_inventory.dispatch(f.office, f.owner, '/inventory/movements', 'GET',
                        {'_query': {'project_id': f.project}})[0]['items'])

    def main(self):
        f = self.f
        f.article = Documents(f.office).save_article(f.owner, f.req(revision=f.article['revision'],
            cost_price_net='10.0000'), f.article['id'])
        result = dict(project_id=f.project, location=deepcopy(f.location), article=deepcopy(f.article))
        receive_command=f.req(kind='receive',article_id=f.article['id'],to_location_id=f.location['id'],
                              quantity='10',unit_cost_net='10.0000',note='Synthetic actual receipt')
        received=f.api.move(f.owner,receive_command)
        issue_command=f.req(kind='issue',article_id=f.article['id'],from_location_id=f.location['id'],
                            project_id=f.project,quantity='6',note='Synthetic six units issued')
        issue=f.api.move(f.owner,issue_command)
        result.update(receive_command=receive_command, receive=received,
                      issue_command=issue_command, issue=issue, before=self.state())
        updated=Documents(f.office).save_article(f.owner, f.req(revision=f.article['revision'],
            cost_price_net='99.0000'), f.article['id'])
        result['updated_article']=updated
        for label, amount in [('first','2'),('second','1'),('final','3')]:
            command=f.req(kind='return',article_id=issue['article_id'],project_id=issue['project_id'],
                to_location_id=f.location['id'],quantity=amount,reversal_of=issue['id'],
                note='Synthetic '+label+' actual return')
            returned=f.api.move(f.owner, command)
            result[label]=dict(command=command, returned=returned, after=self.state())
        result['all_movements']=business_inventory.dispatch(f.office,f.owner,'/inventory/movements','GET',{'_query':{}})[0]['items']
        f.inventory_grant('inventory.write')
        result['operational']=dict(issue=business_inventory.dispatch(f.office,f.tech,
            '/inventory/movements/'+issue['id'],'GET',{'_query':{}})[0],
            movements=business_inventory.dispatch(f.office,f.tech,'/inventory/movements','GET',
                {'_query':{'project_id':f.project}})[0]['items'])
        # This second record provides an actual write receipt without financial read.
        tech_issue=f.api.move(f.owner,f.req(kind='issue',article_id=f.article['id'],
            from_location_id=f.location['id'],project_id=f.project,quantity='1',note='Synthetic operator issue'))
        tech_command=f.req(kind='return',article_id=f.article['id'],to_location_id=f.location['id'],
            project_id=f.project,quantity='1',reversal_of=tech_issue['id'],note='Synthetic operator return')
        result['operational'].update(second_issue=business_inventory.dispatch(f.office,f.tech,
            '/inventory/movements/'+tech_issue['id'],'GET',{'_query':{}})[0],
            command=tech_command,returned=f.api.move(f.tech,tech_command))
        assert result['before']['stock']['on_hand']=='4.0000'
        assert result['first']['after']['stock']['on_hand']=='6.0000'
        assert result['first']['after']['costs']['material_actual_net']=='40.00'
        assert sum(Decimal(result[key]['returned']['cost_net']) for key in ('first','second','final'))==Decimal(issue['cost_net'])
        return result

    def rounding(self):
        f=self.f
        f.api.move(f.owner,f.req(kind='receive',article_id=f.article['id'],to_location_id=f.location['id'],quantity='1',unit_cost_net='1'))
        f.api.move(f.owner,f.req(kind='receive',article_id=f.article['id'],to_location_id=f.location['id'],quantity='2',unit_cost_net='0'))
        issue=f.api.move(f.owner,f.req(kind='issue',article_id=f.article['id'],from_location_id=f.location['id'],project_id=f.project,quantity='3'))
        returns=[]
        for _ in range(3):
            command=f.req(kind='return',article_id=f.article['id'],project_id=f.project,to_location_id=f.location['id'],quantity='1',reversal_of=issue['id'])
            returns.append(dict(command=command,returned=f.api.move(f.owner,command)))
        assert [row['returned']['cost_net'] for row in returns]==['0.3333','0.3333','0.3334']
        return dict(project_id=f.project,location=f.location,article=f.article,issue=issue,returns=returns,after=self.state())
