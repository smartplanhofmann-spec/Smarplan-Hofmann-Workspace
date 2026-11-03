"""Synthetic custom field types, historical meaning, actual permissions and receipts."""
import json
import sqlite3
import unittest

from core import Problem,canonical
from business_custom_fields import CustomFields,validate_integrity,schema_statements,guard_statements,dispatch,methods
from business_personnel_workflow import _sha
from business_foundation import BusinessFoundation
import test_business_maintenance as maintenance


class CustomFieldTests(unittest.TestCase):
    setUpBase=maintenance.MaintenanceTests.setUp
    actor=maintenance.MaintenanceTests.actor
    req=maintenance.MaintenanceTests.req

    def error(self,status,function,*args,**kwargs):
        with self.assertRaises(Problem) as caught:function(*args,**kwargs)
        self.assertEqual(caught.exception.status,status,caught.exception.message)

    def setUp(self):
        self.setUpBase()
        for sql in schema_statements()+guard_statements('sqlite'):self.office.db.execute(sql)
        self.office.db.commit()
        from business_schema import ensure_schema
        ensure_schema(self.office)
        self.fields=CustomFields(self.office)
        self.customer=self.office.project(self.owner,self.project)['customer_id']

    def definition(self,kind='text',entity='project',previous=None,**changes):
        payload=dict(entity_type=entity,label='Synthetic '+kind,help_text='Erfasster Zusatzwert',field_type=kind,
            required=False,active=True,options=[])
        if previous:payload={key:previous[key] for key in payload}
        payload.update(changes)
        body=self.req(revision=previous['revision'] if previous else 0,definition=payload,reason='Geprüfte Definition' if previous else '')
        if previous:body['id']=previous['id']
        return self.fields.save_definition(self.owner,body)

    def save(self,values,entity='project',entity_id=None,actor=None,**changes):
        entity_id=entity_id or self.project;actor=actor or self.owner
        current=self.fields.entity(actor,entity,entity_id)
        body=self.req(revision=current['current']['revision'],definitions_hash=current['definitions_hash'],values=values,reason='Zusatzwerte geprüft')
        body.update(changes)
        return self.fields.save_values(actor,entity,entity_id,body),body

    def test_all_types_exact_precision_no_core_mutation_and_restore_proof(self):
        choice=self.req()['request_id'];definitions=[self.definition(kind,options=[dict(id=choice,label='A',active=True)] if kind=='choice' else []) for kind in ('text','number','date','choice','boolean')]
        core=dict(self.office.db.execute('SELECT * FROM projects WHERE id=?',(self.project,)).fetchone())
        entries=dict(zip([item['id'] for item in definitions],['ä\nMessung','999999999999.123456','2028-02-29',choice,False]))
        result,body=self.save(entries)
        self.assertEqual(self.fields.save_values(self.owner,'project',self.project,body),result)
        self.assertEqual(result['values'][definitions[1]['id']]['value'],'999999999999.123456')
        self.assertEqual(dict(self.office.db.execute('SELECT * FROM projects WHERE id=?',(self.project,)).fetchone()),core)
        self.assertTrue(validate_integrity(self.office))
        self.assertEqual(self.fields.entity(self.tech,'project',self.project)['current'],result)

    def test_explicit_required_and_false_zero_are_valid_without_invented_defaults(self):
        a=self.definition('boolean',required=True);b=self.definition('number',required=True)
        view=self.fields.entity(self.owner,'project',self.project)
        self.assertFalse(view['complete']);self.assertEqual(set(view['missing_required']),{a['id'],b['id']})
        self.error(400,self.save,{a['id']:None,b['id']:'0'})
        self.save({a['id']:False,b['id']:'0'})
        self.assertTrue(self.fields.entity(self.owner,'project',self.project)['complete'])
        extra=self.definition('text',required=True)
        self.assertEqual(self.fields.entity(self.owner,'project',self.project)['missing_required'],[extra['id']])

    def test_archived_definitions_and_options_remain_readable_and_cannot_be_reinterpreted(self):
        a,b=self.req()['request_id'],self.req()['request_id']
        definition=self.definition('choice',options=[dict(id=a,label='Alt',active=True),dict(id=b,label='Neu',active=True)])
        first,_=self.save({definition['id']:a})
        changed=self.definition(previous=definition,options=[dict(id=a,label='Historischer Wert',active=False),dict(id=b,label='Neu',active=True)])
        second,_=self.save({definition['id']:a})
        self.assertEqual(first['values'][definition['id']]['definition']['options'][0]['label'],'Alt')
        self.assertEqual(second['values'][definition['id']]['definition']['options'][0]['label'],'Historischer Wert')
        self.error(409,self.definition,previous=changed,field_type='text',options=[])
        self.error(409,self.definition,previous=changed,options=[dict(id=b,label='Neu',active=True)])
        self.save({definition['id']:b})
        self.error(400,self.save,{definition['id']:a})
        self.definition(previous=changed,active=False)
        last,_=self.save({})
        self.assertEqual(last['values'][definition['id']]['value'],b)
        self.error(400,self.save,{definition['id']:None})
        self.assertTrue(validate_integrity(self.office))

    def test_type_validation_rejects_lossy_numbers_and_ambiguous_inputs(self):
        for kind,bad in [('number',[0,True,'1e2','01','1.1234567','١','1,2']),('boolean',['false',0]),('date',['2026-02-29','2026-1-01']),('text',[3,'bad\x00'])]:
            with self.subTest(kind=kind):
                definition=self.definition(kind)
                for value in bad:self.error(400,self.save,{definition['id']:value})
                self.definition(previous=definition,active=False)

    def test_fresh_entity_permissions_even_on_receipt_and_global_deny(self):
        field=self.definition('text',entity='asset');body_values={field['id']:'Synthetic protected'}
        result,body=self.save(body_values,entity='asset',entity_id=self.asset['id'],actor=self.tech)
        self.assertEqual(self.fields.save_values(self.tech,'asset',self.asset['id'],body),result)
        foundation=BusinessFoundation(self.office)
        foundation.save_grant(self.owner,self.req(user_id=self.tech['id'],permission='documents.write',scope='*',effect='deny',revision=0))
        self.assertFalse(self.fields.entity(self.tech,'asset',self.asset['id'])['can_write'])
        self.error(403,self.fields.save_values,self.tech,'asset',self.asset['id'],body)
        self.office.assign(self.owner,self.project,self.tech['id'],remove=True)
        self.error(404,self.fields.entity,self.tech,'asset',self.asset['id'])
        self.error(403,self.fields.definitions,self.tech)

    def test_contact_scope_project_read_write_separation_and_changed_role(self):
        self.definition('text',entity='contact')
        self.error(403,self.fields.entity,self.tech,'contact',self.customer)
        self.error(403,self.save,{},actor=self.tech)
        manager=self.actor('manager');self.office.assign(self.owner,self.project,manager['id'])
        self.assertTrue(self.fields.entity(manager,'project',self.project)['can_write'])
        self.assertTrue(self.fields.entity(manager,'contact',self.customer)['can_write'])
        self.office.db.execute('UPDATE users SET active=0 WHERE id=?',(manager['id'],))
        self.error(401,self.fields.entity,manager,'project',self.project)

    def test_conflicts_hash_binding_history_pages_and_append_only_guards(self):
        field=self.definition();first,body=self.save({field['id']:'One'})
        changed=self.definition(previous=field,label='Renamed')
        self.assertEqual(self.fields.save_values(self.owner,'project',self.project,body),first)
        with self.assertRaises(Problem) as caught:self.fields.save_values(self.owner,'project',self.project,{**body,'request_id':self.req()['request_id']})
        self.assertEqual(caught.exception.request_resolution,'not_accepted')
        with self.assertRaises(Problem) as caught:self.fields.save_values(self.owner,'project',self.project,{**body,'reason':'Different'})
        self.assertIsNone(getattr(caught.exception,'request_resolution',None))
        second,_=self.save({field['id']:'Two'})
        history=self.fields.history(self.owner,{'limit':'1'},entity_type='project',entity_id=self.project)
        self.assertEqual(history['items'],[second]);self.assertEqual(history['next_before_revision'],2)
        self.assertEqual(self.fields.history(self.owner,{'before_revision':'2'},entity_type='project',entity_id=self.project)['items'],[first])
        for table in ('business_custom_field_definitions','business_custom_field_values','business_custom_field_requests'):
            with self.assertRaises(sqlite3.IntegrityError):self.office.db.execute('DELETE FROM '+table)
        self.assertEqual(self.fields.history(self.owner,{},definition_id=field['id'])['items'],[changed,field])

    def test_rehashed_tamper_of_definition_snapshot_fails_semantic_restore_validation(self):
        field=self.definition();self.save({field['id']:'Original'})
        row=dict(self.office.db.execute('SELECT * FROM business_custom_field_values').fetchone())
        payload=json.loads(row['payload_json']);payload['definitions'][0]['label']='Forged'
        payload['definitions_hash']=_sha(payload['definitions'])
        envelope={key:row[key] for key in ('entity_type','entity_id','revision','previous_hash','created_by','created_at')};envelope['payload']=payload
        self.office.db.execute('DROP TRIGGER business_custom_field_values_update_guard')
        self.office.db.execute('UPDATE business_custom_field_values SET payload_json=?,content_hash=?',(canonical(payload),_sha(envelope)))
        with self.assertRaises(ValueError):validate_integrity(self.office)

    def test_strict_api_methods_queries_and_unknown_keys(self):
        self.assertEqual(methods('/custom-fields/entities/project/'+self.project),'GET, POST')
        self.error(405,dispatch,self.office,self.owner,'/custom-fields/definitions','DELETE',{})
        self.error(400,dispatch,self.office,self.owner,'/custom-fields/definitions','GET',{'_query':{'project_id':self.project}})
        self.error(400,self.fields.history,self.owner,{'limit':'1.1'},entity_type='project',entity_id=self.project)
        self.error(400,self.definition,options=[dict(id=self.req()['request_id'],label='Bad',active=True)])

    def test_archived_contact_and_privacy_erasure_keep_explicit_historical_blocker(self):
        contact=self.office.create_customer(self.owner,dict(name='Synthetic standalone contact',email='standalone@example.test'))
        field=self.definition(entity='contact')
        first,body=self.save({field['id']:'Historical confidential text'},entity='contact',entity_id=contact['id'])
        self.save({field['id']:None},entity='contact',entity_id=contact['id'])
        foundation=BusinessFoundation(self.office)
        current=foundation.contact(self.owner,contact['id'])
        erased=foundation.erase_contact(self.owner,contact['id'],self.req(revision=current['revision'],confirmed=True))
        self.assertEqual(erased['status'],'blocked')
        self.assertTrue(any('Zusatzfelder' in message for message in erased['blockers']))
        with self.office.db:self.office.db.execute('UPDATE customers SET active=0 WHERE id=?',(contact['id'],))
        self.assertFalse(self.fields.entity(self.owner,'contact',contact['id'])['can_write'])
        self.error(409,self.fields.save_values,self.owner,'contact',contact['id'],body)
        self.assertEqual(self.fields.history(self.owner,{},entity_type='contact',entity_id=contact['id'])['items'][-1],first)

    def test_compatibility_readonly_preserves_history_and_blocks_even_original_write_replay(self):
        from business_schema import set_mode
        field=self.definition();first,body=self.save({field['id']:'Saved before compatibility mode'})
        set_mode(self.office,'legacy')
        self.assertEqual(self.fields.entity(self.owner,'project',self.project)['current'],first)
        self.assertFalse(self.fields.entity(self.owner,'project',self.project)['can_write'])
        self.error(409,self.fields.save_values,self.owner,'project',self.project,body)
        set_mode(self.office,'business')
        self.assertEqual(self.fields.save_values(self.owner,'project',self.project,body),first)


if __name__=='__main__':unittest.main()
