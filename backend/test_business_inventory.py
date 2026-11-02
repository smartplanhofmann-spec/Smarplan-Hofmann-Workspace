"""Persisted synthetic stock ledger, reservation and project cost contracts."""
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest
import uuid
import threading

from core import Office, Problem
from business_inventory import BusinessInventory, schema_statements, validate_integrity
from business_documents import Documents, schema_statements as document_schema
from business_operations import schema_statements as operation_schema


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.office=Office(Path(self.temp.name)/'office.db'); self.addCleanup(self.office.db.close)
        from business_foundation import schema_statements as foundation_schema
        from business_time import schema_statements as time_schema
        from business_planning import schema_statements as planning_schema
        for statement in foundation_schema('BLOB')+document_schema('BLOB')+operation_schema('BLOB')+planning_schema('BLOB')+time_schema('BLOB')+schema_statements('BLOB'):
            self.office.db.execute(statement)
        self.office.db.commit()
        self.owner=self.actor('owner'); self.tech=self.actor('technician')
        self.project=self.office.add_project(self.owner,'Synthetic fit-out','Synthetic customer')
        self.office.assign(self.owner,self.project,self.tech['id'])
        self.api=BusinessInventory(self.office,clock=lambda:datetime(2026,10,25,10,tzinfo=timezone.utc))
        self.location=self.api.save_location(self.owner,self.req(name='Synthetic main store'))
        self.van=self.api.save_location(self.owner,self.req(name='Synthetic van'))
        self.article=Documents(self.office).save_article(self.owner,self.req(code='SYN-CABLE',name='Synthetic cable',kind='material',unit='m',unit_price_net='3.0000',cost_price_net='1.2500',tax_rate='19',tax_category='S',currency='EUR',active=True))
        self.office.db.commit()

    def actor(self,role):
        email=uuid.uuid4().hex+'@example.test'; return dict(id=self.office.add_user(email,'Synthetic-password-123',role),role=role,email=email)

    def req(self,**data): return dict(request_id=uuid.uuid4().hex,**data)

    def error(self,status,function,*args):
        with self.assertRaises(Problem) as caught: function(*args)
        self.assertEqual(caught.exception.status,status,caught.exception.message)

    def receive(self,quantity='10',cost='1.2500'):
        return self.api.move(self.owner,self.req(kind='receive',article_id=self.article['id'],to_location_id=self.location['id'],quantity=quantity,unit_cost_net=cost))

    def calculated_article(self, *, kind='material'):
        documents=Documents(self.office)
        inputs=dict(base_cost_net='12.34',labor_hours='2',hourly_cost_net='20',overhead_percent='10',
            markup_percent='25',quantity='1',kind=kind,unit='m',source_article_id=self.article['id'],
            source_article_revision=self.article['revision'])
        if kind=='service':
            inputs['components']=[dict(article_id=self.article['id'],article_revision=self.article['revision'],quantity='2')]
        preview=documents.pricing_preview(self.owner,inputs)
        article=documents.save_article(self.owner,self.req(name='Calculated '+kind,code='CALC-'+kind,
            pricing=preview['inputs'],pricing_hash=preview['preview_hash'],price_confirmation=True))
        self.assertEqual(article['pricing_snapshot'],preview)
        self.assertGreater(float(preview['totals']['profit_net']),0)
        return article

    def assert_operational_article(self, value, article):
        fields=('id','revision','code','name','kind','unit','active')
        self.assertEqual(value,{key:article[key] for key in fields})

    def inventory_grant(self, permission, *, effect='allow', revision=0):
        from business_foundation import BusinessFoundation
        return BusinessFoundation(self.office).save_grant(self.owner,self.req(user_id=self.tech['id'],
            permission=permission,scope='*',effect=effect,revision=revision))

    def test_real_calculated_article_scan_hides_prices_and_bom_without_changing_finance_view(self):
        import business_inventory as domain
        for kind in ('material','service'):
            article=self.calculated_article(kind=kind)
            if kind=='service':
                self.assertTrue(article['components'])
                self.assertTrue(article['pricing_snapshot']['components'])
            query={'_query':{'code':article['code']}}
            public=domain.dispatch(self.office,self.tech,'/inventory/scan','GET',query)[0]
            self.assert_operational_article(public,article)
            private=domain.dispatch(self.office,self.owner,'/inventory/scan','GET',query)[0]
            self.assertEqual(private,self.api._article(article['id']) if kind=='material' else {
                key:value for key,value in article.items() if key!='updated_at'})
            self.assertEqual(private['pricing_snapshot'],article['pricing_snapshot'])

    def test_real_calculated_article_draft_post_and_replay_hide_complete_commercial_snapshot(self):
        import business_inventory as domain
        from business_purchasing import Purchasing
        article=self.calculated_article()
        self.inventory_grant('inventory.write')
        body=self.req(project_id=self.project,supplier_name='Synthetic supplier',status='draft',
            items=[dict(article_id=article['id'],quantity='3.5')])
        first=domain.dispatch(self.office,self.tech,'/inventory/orders','POST',body)[0]
        self.assert_operational_article(first['items'][0]['article_snapshot'],article)
        self.assertEqual((first['items'][0]['quantity'],first['status'],first['delivery_status']),('3.5000','draft','not_sent'))
        self.assertEqual(domain.dispatch(self.office,self.tech,'/inventory/orders','POST',body)[0],first)
        self.inventory_grant('finance.read')
        rich_body={**body,'request_id':uuid.uuid4().hex}
        rich=domain.dispatch(self.office,self.tech,'/inventory/orders','POST',rich_body)[0]
        self.assertEqual(rich['items'][0]['article_snapshot']['pricing_snapshot'],article['pricing_snapshot'])
        self.inventory_grant('finance.read',effect='deny',revision=1)
        replay=domain.dispatch(self.office,self.tech,'/inventory/orders','POST',rich_body)[0]
        self.assertEqual(replay['id'],rich['id'])
        self.assert_operational_article(replay['items'][0]['article_snapshot'],article)
        read=Purchasing(self.office).get(self.tech,rich['id'])
        self.assertEqual((read['items'][0]['unit'],read['items'][0]['ordered_quantity']),('m','3.5000'))
        self.assertNotIn('pricing_snapshot',json.dumps(read))
        stored=json.loads(self.office.db.execute('SELECT payload_json FROM business_purchase_orders WHERE id=?',(rich['id'],)).fetchone()[0])
        self.assertEqual(stored[0]['article_snapshot']['pricing_snapshot'],article['pricing_snapshot'])

    def test_calculated_stock_get_post_and_replays_recheck_finance_for_every_snapshot(self):
        import business_inventory as domain
        self.article=self.calculated_article()
        self.receive()
        self.inventory_grant('inventory.write')
        self.inventory_grant('finance.read')
        reserve_body=self.req(article_id=self.article['id'],location_id=self.location['id'],quantity='3')
        reservation=self.api.reserve(self.tech,self.project,reserve_body)
        transfer_body=self.req(kind='transfer',article_id=self.article['id'],from_location_id=self.location['id'],
            to_location_id=self.van['id'],quantity='1')
        transfer=self.api.move(self.tech,transfer_body)
        pick_body=self.req(items=[dict(reservation_id=reservation['id'],quantity='1')])
        picked=self.api.pick(self.tech,self.project,pick_body)
        for value in (reservation,transfer,picked['items'][0]):
            self.assertEqual(value['article_snapshot']['pricing_snapshot'],self.article['pricing_snapshot'])
        self.inventory_grant('finance.read',effect='deny',revision=1)
        before=[tuple(row) for row in self.office.db.execute('SELECT * FROM business_stock_movements ORDER BY sequence_number')]
        for action,original in ((lambda:self.api.reserve(self.tech,self.project,reserve_body),reservation),
                (lambda:self.api.move(self.tech,transfer_body),transfer),
                (lambda:self.api.pick(self.tech,self.project,pick_body)['items'][0],picked['items'][0])):
            result=action()
            self.assertEqual(result['id'],original['id'])
            self.assert_operational_article(result['article_snapshot'],self.article)
            self.assertNotIn('unit_cost_net',result)
            self.assertNotIn('cost_net',result)
        fresh=self.api.reserve(self.tech,self.project,self.req(article_id=self.article['id'],location_id=self.location['id'],quantity='1'))
        self.assert_operational_article(fresh['article_snapshot'],self.article)
        for path,query in (('/inventory/movements',{}),('/inventory/movements/'+transfer['id'],{}),
                ('/inventory/reservations',{'project_id':self.project}),
                ('/inventory/reservations/'+reservation['id'],{'project_id':self.project})):
            result=domain.dispatch(self.office,self.tech,path,'GET',{'_query':query})[0]
            for value in result.get('items',[result]):
                self.assert_operational_article(value['article_snapshot'],self.article)
                self.assertNotIn('unit_cost_net',value)
                self.assertNotIn('cost_net',value)
        row=self.office.db.execute('SELECT * FROM business_stock_movements WHERE id=?',(transfer['id'],)).fetchone()
        self.assert_operational_article(self.api._movement(row,financial=False)['article_snapshot'],self.article)
        self.assertEqual(self.api._movement(row)['article_snapshot']['pricing_snapshot'],self.article['pricing_snapshot'])
        self.assertEqual([tuple(row) for row in self.office.db.execute('SELECT * FROM business_stock_movements ORDER BY sequence_number')],before)
        self.assertTrue(validate_integrity(self.office))

    def test_journal_receive_transfer_issue_return_preserves_historical_cost(self):
        self.receive()
        body=self.req(kind='transfer',article_id=self.article['id'],from_location_id=self.location['id'],to_location_id=self.van['id'],quantity='4')
        transfer=self.api.move(self.owner,body)
        self.assertEqual(self.api.move(self.owner,body),transfer)
        issue=self.api.move(self.owner,self.req(kind='issue',article_id=self.article['id'],from_location_id=self.van['id'],project_id=self.project,quantity='3'))
        self.assertEqual(issue['cost_net'],'3.7500')
        self.api.move(self.owner,self.req(kind='return',article_id=self.article['id'],to_location_id=self.van['id'],project_id=self.project,quantity='1',reversal_of=issue['id']))
        self.assertEqual(self.api.balance(self.owner,self.van['id'],self.article['id'])['on_hand'],'2.0000')
        self.assertEqual(self.api.balance(self.owner,self.location['id'],self.article['id'])['on_hand'],'6.0000')
        self.assertTrue(validate_integrity(self.office))

    def test_reservations_partial_picking_and_retry_cannot_overbook_or_double_issue(self):
        self.receive()
        reservation=self.api.reserve(self.owner,self.project,self.req(article_id=self.article['id'],location_id=self.location['id'],quantity='7'))
        self.error(409,self.api.reserve,self.owner,self.project,self.req(article_id=self.article['id'],location_id=self.location['id'],quantity='4'))
        self.error(409,self.api.move,self.owner,self.req(kind='issue',article_id=self.article['id'],from_location_id=self.location['id'],project_id=self.project,quantity='4'))
        body=self.req(items=[{'reservation_id':reservation['id'],'quantity':'3'}])
        picked=self.api.pick(self.owner,self.project,body)
        self.assertEqual(self.api.pick(self.owner,self.project,body),picked)
        stock=self.api.balance(self.owner,self.location['id'],self.article['id'])
        self.assertEqual((stock['on_hand'],stock['reserved'],stock['available']),('7.0000','4.0000','3.0000'))
        self.error(409,self.api.pick,self.owner,self.project,self.req(items=[{'reservation_id':reservation['id'],'quantity':'5'}]))
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM business_stock_movements WHERE kind='issue'").fetchone()[0],1)
        self.assertTrue(validate_integrity(self.office))

    def test_later_article_price_update_never_revalues_previous_stock_or_issue(self):
        self.receive()
        changed=Documents(self.office).save_article(self.owner,self.req(revision=self.article['revision'],cost_price_net='9.0000'),self.article['id'])
        issued=self.api.move(self.owner,self.req(kind='issue',article_id=self.article['id'],from_location_id=self.location['id'],project_id=self.project,quantity='2'))
        self.assertEqual(issued['cost_net'],'2.5000')
        self.assertEqual(issued['article_snapshot']['revision'],changed['revision'])
        self.assertEqual(issued['unit_cost_net'],'1.2500')

    def test_scan_only_looks_up_and_reorder_is_local_proposal(self):
        self.receive('2')
        self.api.set_reorder_rule(self.owner,self.req(location_id=self.location['id'],article_id=self.article['id'],minimum='3',target='10'))
        before=self.office.db.execute('SELECT COUNT(*) FROM business_stock_movements').fetchone()[0]
        found=self.api.lookup(self.tech,'SYN-CABLE')
        self.assertEqual(found['id'],self.article['id'])
        self.assertNotIn('cost_price_net',found)
        suggestions=self.api.reorder_suggestions(self.owner)
        self.assertEqual(suggestions[0]['suggested_quantity'],'8.0000')
        self.assertEqual(suggestions[0]['status'],'proposal')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_stock_movements').fetchone()[0],before)

    def test_budget_changes_are_separate_approved_snapshots_and_financial_scope_is_enforced(self):
        self.receive()
        self.api.move(self.owner,self.req(kind='issue',article_id=self.article['id'],from_location_id=self.location['id'],project_id=self.project,quantity='2'))
        budget=self.api.save_budget(self.owner,self.project,self.req(material_net='10.00',labor_net='20.00',machine_net='0.00',other_net='0.00'))
        self.api.add_change_order(self.owner,self.project,self.req(title='Synthetic extension',amount_net='5.00',approved=False))
        change=self.api.add_change_order(self.owner,self.project,self.req(title='Confirmed extension',amount_net='3.00',approved=True))
        # Time module can have no approved source entries; it must not invent costs.
        report=self.api.cost_report(self.owner,self.project)
        self.assertEqual((report['budget_net'],report['approved_changes_net'],report['material_actual_net']),('30.00','3.00','2.50'))
        self.assertEqual(report['budget_revision'],budget['revision'])
        self.assertEqual(report['approved_changes'][0]['id'],change['id'])
        self.error(403,self.api.cost_report,self.tech,self.project)
        self.error(403,self.api.move,self.tech,self.req(kind='receive',article_id=self.article['id'],to_location_id=self.location['id'],quantity='1'))
        self.assertTrue(validate_integrity(self.office))

    def test_competing_connections_cannot_reserve_more_than_canonical_stock(self):
        self.receive('5')
        second=Office(Path(self.temp.name)/'office.db')
        barrier=threading.Barrier(2)
        def reserve(api):
            barrier.wait(timeout=5)
            try: return api.reserve(self.owner,self.project,self.req(article_id=self.article['id'],location_id=self.location['id'],quantity='4'))
            except Problem as error: return error.status
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                outcomes=list(pool.map(reserve,(self.api,BusinessInventory(second))))
            self.assertEqual(sum(isinstance(result,dict) for result in outcomes),1)
            self.assertIn(409,outcomes)
            self.assertEqual(self.api.balance(self.owner,self.location['id'],self.article['id'])['reserved'],'4.0000')
        finally: second.db.close()
        self.assertTrue(validate_integrity(self.office))

    def test_partial_batch_pick_failure_rolls_back_first_item_receipt_and_movement(self):
        self.receive()
        reservation=self.api.reserve(self.owner,self.project,self.req(article_id=self.article['id'],location_id=self.location['id'],quantity='7'))
        body=self.req(items=[{'reservation_id':reservation['id'],'quantity':'2'},{'reservation_id':'f'*32,'quantity':'1'}])
        self.error(404,self.api.pick,self.owner,self.project,body)
        self.assertEqual(self.api.balance(self.owner,self.location['id'],self.article['id'])['on_hand'],'10.0000')
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM business_stock_movements WHERE kind='issue'").fetchone()[0],0)
        self.assertIsNone(self.office.db.execute('SELECT 1 FROM business_inventory_requests WHERE request_id=?',(body['request_id'],)).fetchone())

    def test_replay_after_financial_grant_withdrawal_redacts_existing_snapshot(self):
        self.receive()
        with self.office.db:
            for permission in ('inventory.write','finance.read'):
                self.office.db.execute('INSERT INTO business_permission_grants(id,user_id,permission,scope,effect,revision,updated_by,updated_at) VALUES(?,?,?,?,?,1,?,?)',(uuid.uuid4().hex,self.tech['id'],permission,'*','allow',self.owner['id'],self.api.now()))
        body=self.req(article_id=self.article['id'],location_id=self.location['id'],quantity='2')
        first=self.api.reserve(self.tech,self.project,body)
        self.assertIn('cost_price_net',first['article_snapshot'])
        with self.office.db:
            self.office.db.execute("DELETE FROM business_permission_grants WHERE user_id=? AND permission='finance.read'",(self.tech['id'],))
        replay=self.api.reserve(self.tech,self.project,body)
        self.assertNotIn('cost_price_net',replay['article_snapshot'])
        self.assertNotIn('unit_price_net',replay['article_snapshot'])
        self.assertEqual(first['id'],replay['id'])

    def test_global_movement_list_filters_project_scope_and_all_price_paths(self):
        import business_inventory as domain
        self.receive()
        other=self.office.add_project(self.owner,'Private job','Private customer')
        private=self.api.move(self.owner,self.req(kind='issue',article_id=self.article['id'],from_location_id=self.location['id'],project_id=other,quantity='1',note='Private project details'))
        result=domain.dispatch(self.office,self.tech,'/inventory/movements','GET',{})[0]
        self.assertNotIn(private['id'],{row['id'] for row in result['items']})
        self.assertNotIn('cost_price_net',json.dumps(result))
        self.assertNotIn('unit_cost_net',json.dumps(result))

    def test_fractional_weighted_cost_rounding_does_not_leave_value_without_stock(self):
        self.receive('1','0.0001'); self.receive('2','0.0002')
        self.api.move(self.owner,self.req(kind='issue',article_id=self.article['id'],from_location_id=self.location['id'],project_id=self.project,quantity='1'))
        self.api.move(self.owner,self.req(kind='issue',article_id=self.article['id'],from_location_id=self.location['id'],project_id=self.project,quantity='2'))
        stock=self.api.balance(self.owner,self.location['id'],self.article['id'])
        self.assertEqual((stock['on_hand'],stock['stock_value_net']),('0.0000','0.00'))
        self.assertTrue(validate_integrity(self.office))

    def test_real_approved_time_and_article_sources_flow_into_costs_and_diary_without_payroll_leak(self):
        from business_planning import Planning
        from business_time import TimeTracking
        from business_operations import BusinessOperations,validate_integrity as validate_operations
        now=datetime(2026,10,26,20,tzinfo=timezone.utc)
        planning=Planning(self.office,clock=lambda:now)
        employee=planning.save_employee(self.owner,self.req(user_id=self.tech['id'],name='Synthetic employee',weekly_minutes=2400,hourly_cost_minor=3500))
        timer=TimeTracking(self.office,clock=lambda:now); entry_id=uuid.uuid4().hex
        timer.event(self.tech,self.req(entry_id=entry_id,project_id=self.project,device_id='synthetic-device',sequence=1,revision=0,action='start',occurred_at='2026-10-26T08:00:00+01:00'))
        timer.event(self.tech,self.req(entry_id=entry_id,project_id=self.project,device_id='synthetic-device',sequence=2,revision=1,action='stop',occurred_at='2026-10-26T10:00:00+01:00'))
        self.assertEqual(self.api.cost_report(self.owner,self.project)['labor_actual_net'],'0.00')
        summary=timer.summary(self.owner,{'employee_id':employee['id'],'from':'2026-10-26','to':'2026-10-26'})
        timer.approve_day(self.owner,'2026-10-26',self.req(employee_id=employee['id'],revision=summary['days'][0]['revision']))
        planning.save_employee(self.owner,self.req(id=employee['id'],revision=employee['revision'],hourly_cost_minor=9900))
        costs=self.api.cost_report(self.owner,self.project)
        self.assertEqual(costs['labor_actual_net'],'70.00')
        ops=BusinessOperations(self.office,clock=lambda:now)
        diary=ops.save_entry(self.tech,self.project,'diary',self.req(title='Imported actual work',article_lines=[{'article_id':self.article['id'],'quantity':'2'}],time_references=[{'entry_id':entry_id,'work_date':'2026-10-26'}]))
        self.assertEqual(diary['imported_net_seconds'],7200)
        self.assertEqual(diary['article_lines'][0]['article_revision'],self.article['revision'])
        self.assertNotIn('hourly_cost',json.dumps(diary)); self.assertNotIn('cost_price',json.dumps(diary))
        Documents(self.office).save_article(self.owner,self.req(revision=self.article['revision'],name='Later catalogue name'),self.article['id'])
        revised=ops.save_entry(self.tech,self.project,'diary',self.req(revision=1,notes='Later note'),diary['id'])
        self.assertEqual(revised['article_lines'][0]['name'],'Synthetic cable')
        self.assertEqual(ops.export_project(self.tech,self.project)['entries'],[revised])
        self.assertTrue(validate_operations(self.office))

    def test_missing_time_cost_rate_is_incomplete_and_never_claims_remaining_budget(self):
        from business_planning import Planning
        from business_time import TimeTracking
        now=datetime(2026,10,26,20,tzinfo=timezone.utc)
        employee=Planning(self.office,clock=lambda:now).save_employee(self.owner,self.req(user_id=self.tech['id'],name='Unpriced synthetic employee',weekly_minutes=2400))
        timer=TimeTracking(self.office,clock=lambda:now); entry_id=uuid.uuid4().hex
        timer.event(self.tech,self.req(entry_id=entry_id,project_id=self.project,device_id='synthetic-unpriced',sequence=1,revision=0,action='start',occurred_at='2026-10-26T08:00:00+01:00'))
        timer.event(self.tech,self.req(entry_id=entry_id,project_id=self.project,device_id='synthetic-unpriced',sequence=2,revision=1,action='stop',occurred_at='2026-10-26T10:00:00+01:00'))
        summary=timer.summary(self.owner,{'employee_id':employee['id'],'from':'2026-10-26','to':'2026-10-26'})
        timer.approve_day(self.owner,'2026-10-26',self.req(employee_id=employee['id'],revision=summary['days'][0]['revision']))
        self.api.save_budget(self.owner,self.project,self.req(labor_net='100.00'))
        report=self.api.cost_report(self.owner,self.project)
        self.assertFalse(report['costs_complete'])
        self.assertEqual(report['missing_rates_count'],1)
        self.assertIsNone(report['remaining_net'])

    def test_unconfigured_zero_material_price_requires_an_explicit_financial_confirmation(self):
        Documents(self.office).save_article(self.owner,self.req(revision=self.article['revision'],cost_price_net='0'),self.article['id'])
        body=self.req(kind='receive',article_id=self.article['id'],to_location_id=self.location['id'],quantity='1')
        self.error(400,self.api.move,self.owner,body)
        confirmed=self.api.move(self.owner,self.req(kind='receive',article_id=self.article['id'],to_location_id=self.location['id'],quantity='1',unit_cost_net='0'))
        self.assertEqual(confirmed['cost_net'],'0.0000')

    def test_proposed_change_order_requires_separate_retry_safe_approval_and_preserves_original_proposal(self):
        proposed=self.api.add_change_order(self.owner,self.project,self.req(title='Extra outlet',amount_net='45.00',approved=False))
        self.assertEqual(self.api.cost_report(self.owner,self.project)['approved_changes_net'],'0.00')
        self.error(403,self.api.approve_change_order,self.tech,self.project,proposed['id'],self.req(revision=1))
        body=self.req(revision=1)
        approved=self.api.approve_change_order(self.owner,self.project,proposed['id'],body)
        self.assertEqual(self.api.approve_change_order(self.owner,self.project,proposed['id'],body),approved)
        self.assertEqual(self.api.cost_report(self.owner,self.project)['approved_changes_net'],'45.00')
        self.assertEqual((approved['revision'],approved['title'],approved['amount_net']),(2,proposed['title'],proposed['amount_net']))
        self.assertEqual(self.office.db.execute("SELECT COUNT(*) FROM audit WHERE action='business.change_order.approved'").fetchone()[0],1)
        self.assertTrue(validate_integrity(self.office))
        second=self.api.add_change_order(self.owner,self.project,self.req(title='Unapproved',amount_net='10.00',approved=False))
        with self.office.db: self.office.db.execute('UPDATE business_change_orders SET approved=1 WHERE id=?',(second['id'],))
        with self.assertRaises(ValueError): validate_integrity(self.office)

    def test_approved_dst_day_longer_than_24_hours_retains_valid_diary_provenance(self):
        from business_planning import Planning
        from business_time import TimeTracking
        from business_operations import BusinessOperations,validate_integrity as validate_operations
        now=datetime(2026,10,26,20,tzinfo=timezone.utc)
        employee=Planning(self.office,clock=lambda:now).save_employee(self.owner,self.req(user_id=self.tech['id'],name='Synthetic DST fixture',weekly_minutes=2400,hourly_cost_minor=3500))
        timer=TimeTracking(self.office,clock=lambda:now); entry_id=uuid.uuid4().hex
        timer.event(self.tech,self.req(entry_id=entry_id,project_id=self.project,device_id='synthetic-dst',sequence=1,revision=0,action='start',occurred_at='2026-10-25T00:00:00+02:00'))
        timer.event(self.tech,self.req(entry_id=entry_id,project_id=self.project,device_id='synthetic-dst',sequence=2,revision=1,action='stop',occurred_at='2026-10-26T00:00:00+01:00'))
        summary=timer.summary(self.owner,{'employee_id':employee['id'],'from':'2026-10-25','to':'2026-10-25'})
        timer.approve_day(self.owner,'2026-10-25',self.req(employee_id=employee['id'],revision=summary['days'][0]['revision']))
        diary=BusinessOperations(self.office).save_entry(self.tech,self.project,'diary',self.req(title='Synthetic calendar proof',time_references=[{'entry_id':entry_id,'work_date':'2026-10-25'}]))
        self.assertGreater(diary['imported_net_seconds'],86400)
        self.assertTrue(validate_operations(self.office))

if __name__=='__main__': unittest.main()
