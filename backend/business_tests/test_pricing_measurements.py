"""Real Decimal, SQL and authenticated HTTP checks for E3/E4/K2.

No invoice-issuing policy is replaced: these cases create ordinary draft
documents and, for the frozen provenance check, an ordinary final offer.
"""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import patch

from core import Office, Problem
from business_documents import Documents, _buyer, render_prepared, validate_integrity
from business_operations import BusinessOperations
from business_schema import ensure_schema


def request(**fields):
    return dict(request_id=uuid.uuid4().hex, **fields)


class PricingFixture:
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='synthetic-pricing-')
        self.addCleanup(temporary.cleanup)
        self.office=Office(Path(temporary.name)/'office.db')
        self.addCleanup(self.office.db.close)
        ensure_schema(self.office, activate=True)
        self.owner=dict(id=self.office.add_user('owner@example.test','Synthetic-password-123','owner'),role='owner')
        self.project=self.office.add_project(self.owner,'Synthetic project','Synthetic customer')
        self.other=self.office.add_project(self.owner,'Other project','Other customer')
        self.api=Documents(self.office,clock=lambda:datetime(2030,1,10,12,tzinfo=timezone.utc))
        self.operations=BusinessOperations(self.office)

    def article(self, **changes):
        return self.api.save_article(self.owner,request(name='Synthetic material',kind='material',unit='C62',
            unit_price_net='8',cost_price_net='5',tax_rate='19',**changes))

    def preview(self, **changes):
        return self.api.pricing_preview(self.owner,request(project_id=self.project,base_cost_net='10',labor_hours='2',
            hourly_cost_net='20',overhead_percent='10',markup_percent='20',quantity='2',**changes))

    def adoption(self, preview, **changes):
        return dict(description='Kalkulierte Leistung',quantity=preview['inputs']['quantity'],pricing=preview['inputs'],
            pricing_hash=preview['preview_hash'],price_confirmation=True,**changes)

    def draft(self, **changes):
        value=dict(project_id=self.project,kind='offer',issue_date='2030-01-10',
            buyer=dict(name='Synthetic buyer',address_line='Testweg 1',postal_code='10115',city='Berlin',country='DE'),
            positions=[dict(description='Synthetic',quantity='1',unit='C62',unit_price_net='10',tax_rate='19')])
        value.update(changes)
        return self.api.create(self.owner,request(**value))

    def problem(self,status,action):
        with self.assertRaises(Problem) as error:action()
        self.assertEqual(status,error.exception.status)

    def measurement(self, units=('m2',)):
        lines=[dict(description='Synthetic '+unit,unit=unit,formula='q',variables={'q':{'value':'6.82','unit':unit}}) for unit in units]
        return self.operations.save_entry(self.owner,self.project,'measurement',request(title='Synthetic measurement',lines=lines))

    def transfer(self, source, **changes):
        value=dict(project_id=self.project,measurement_id=source['id'],measurement_revision=source['revision'],
            measurement_hash=source['content_hash'],lines=[dict(line_index=0,unit_price_net='25.50',tax_rate='19',kind='service')])
        value.update(changes)
        return value


class PricingTests(PricingFixture,unittest.TestCase):
    def scoped_finance_actor(self):
        from business_foundation import BusinessFoundation
        actor=dict(id=self.office.add_user('technician@example.test','Synthetic-password-123','technician'),role='technician')
        self.office.assign(self.owner,self.project,actor['id'])
        foundation=BusinessFoundation(self.office)
        for permission in ('finance.read','finance.write'):
            foundation.save_grant(self.owner,request(user_id=actor['id'],permission=permission,scope=self.project,effect='allow',revision=0))
        return actor

    def test_scoped_finance_does_not_grant_live_global_bom_or_source_article_costs(self):
        actor=self.scoped_finance_actor();article=self.article()
        self.problem(403,lambda:self.api.articles(actor))
        manual=self.api.pricing_preview(actor,dict(project_id=self.project,base_cost_net='3'))
        self.assertEqual(manual['unit_cost_net'],'3.00')
        self.problem(403,lambda:self.api.pricing_preview(actor,dict(project_id=self.project,
            components=[dict(article_id=article['id'],article_revision=1,quantity='1')])))
        self.problem(403,lambda:self.api.pricing_preview(actor,dict(project_id=self.project,
            source_article_id=article['id'],source_article_revision=1)))

    def test_scoped_finance_cannot_import_live_global_articles_but_keeps_frozen_documents(self):
        actor=self.scoped_finance_actor();article=self.article()
        body=dict(project_id=self.project,kind='offer',issue_date='2030-01-10',
            positions=[dict(article_id=article['id'],article_revision=1,quantity='1')])
        self.problem(403,lambda:self.api.create(actor,request(**body)))
        manual={**body,'positions':[dict(description='Manual project price',quantity='1',unit='C62',unit_price_net='5',tax_rate='19')]}
        self.api.create(actor,request(**manual))
        frozen=self.api.create(self.owner,request(**body))
        updated=self.api.update(actor,frozen['id'],request(revision=1,title='Project-scoped edit'))
        converted=self.api.convert(actor,updated['id'],request(revision=2,target_kind='order_confirmation'))
        self.assertEqual(converted['positions'],frozen['positions'])

    def test_scoped_finance_cannot_import_a_live_template_but_keeps_existing_template_snapshot(self):
        actor=self.scoped_finance_actor()
        template=self.api.save_template(self.owner,request(name='Private global template',kind='offer',title='Private template',
            positions=[dict(description='Global private template cost',quantity='1',unit='C62',unit_price_net='100',cost_price_net='73.25',tax_rate='19')]))
        self.problem(403,lambda:self.api.templates(actor))
        body=dict(project_id=self.project,kind='offer',issue_date='2030-01-10',template_id=template['id'],template_revision=1)
        self.problem(403,lambda:self.api.create(actor,request(**body)))
        frozen=self.api.create(self.owner,request(**body))
        self.api.save_template(self.owner,request(revision=1,title='Changed global template'),template['id'])
        updated=self.api.update(actor,frozen['id'],request(revision=1,title='Scoped document edit'))
        self.assertEqual(updated['template_source'],frozen['template_source'])
        converted=self.api.convert(actor,updated['id'],request(revision=2,target_kind='order_confirmation'))
        self.assertEqual(converted['template_source'],frozen['template_source'])

    def test_decimal_bom_labor_overhead_markup_surcharge_and_tax_are_readonly(self):
        article=self.article()
        changes=self.office.db.total_changes
        preview=self.preview(components=[dict(article_id=article['id'],article_revision=1,quantity='2')],
            markup_amount='1',surcharge_percent='5',surcharge_amount='2')
        self.assertEqual(self.office.db.total_changes,changes)
        self.assertEqual(preview,self.preview(components=[dict(article_id=article['id'],article_revision=1,quantity='2')],
            markup_amount='1',surcharge_percent='5',surcharge_amount='2'))
        self.assertEqual(preview['unit_cost_net'],'66.00')
        self.assertEqual(preview['unit_price_net'],'85.50')
        self.assertEqual(preview['breakdown']['labor_cost_net'],'40.00')
        self.assertEqual(preview['breakdown']['component_cost_net'],'10.00')
        self.assertEqual(preview['totals']['net'],'171.00')
        self.assertEqual(preview['totals']['tax'],'32.49')
        self.assertEqual(preview['totals']['profit_net'],'39.00')

    def test_rounding_and_invalid_decimal_values_never_become_floats(self):
        value=self.api.pricing_preview(self.owner,dict(base_cost_net='0.005',tax_rate='0'))
        self.assertEqual(value['unit_cost_net'],'0.01')
        for invalid in (1.2,'NaN','Infinity','-1','1e10',True):
            with self.subTest(invalid=invalid):
                self.problem(400,lambda:self.api.pricing_preview(self.owner,dict(base_cost_net=invalid)))
        for invalid in ('0','-1'):
            self.problem(400,lambda:self.api.pricing_preview(self.owner,dict(quantity=invalid)))

    def test_article_and_document_adoption_require_confirmation_and_fresh_bom_revision(self):
        article=self.article()
        preview=self.preview(components=[dict(article_id=article['id'],article_revision=1,quantity='2')])
        unconfirmed=self.adoption(preview);unconfirmed['price_confirmation']=False
        self.problem(400,lambda:self.draft(positions=[unconfirmed]))
        self.api.save_article(self.owner,request(revision=1,cost_price_net='7'),article['id'])
        self.problem(409,lambda:self.draft(positions=[self.adoption(preview)]))
        self.problem(409,lambda:self.api.save_article(self.owner,request(name='Service',kind='service',unit='C62',
            pricing=preview['inputs'],pricing_hash=preview['preview_hash'],price_confirmation=True)))

    def test_confirmed_price_is_persisted_and_snapshot_survives_unrelated_article_change(self):
        article=self.article();preview=self.preview(source_article_id=article['id'],source_article_revision=1)
        draft=self.draft(positions=[self.adoption(preview)])
        self.api.save_article(self.owner,request(revision=1,name='Changed upstream'),article['id'])
        changed=self.api.update(self.owner,draft['id'],request(revision=1,title='New title'))
        self.assertEqual(changed['positions'][0]['pricing_snapshot'],preview)
        calculation=self.api.document_calculation(self.owner,dict(revision=2),draft['id'])
        self.assertEqual(calculation['cost_summary']['known_cost_net'],'110.00')
        self.assertEqual(calculation['profit_net'],'22.00')

    def test_article_adoption_persists_real_vk_cost_and_manual_changes_remove_the_proof(self):
        preview=self.api.pricing_preview(self.owner,dict(base_cost_net='50',markup_percent='20',kind='service',unit='HUR'))
        article=self.api.save_article(self.owner,request(name='Calculated service',pricing=preview['inputs'],
            pricing_hash=preview['preview_hash'],price_confirmation=True))
        self.assertEqual((article['unit_price_net'],article['cost_price_net']),('60.00','50.00'))
        self.assertEqual(article['pricing_snapshot'],preview)
        self.assertTrue(article['cost_known'])
        changed=self.api.save_article(self.owner,request(revision=1,tax_rate='7'),article['id'])
        self.assertNotIn('pricing_snapshot',changed)
        for change in ({'discount_percent':'5'},{'tax_category':'AE','tax_exemption_reason':'Reverse charge'},
                       {'price_base_quantity':'bad'}):
            self.problem(400,lambda:self.draft(positions=[self.adoption(preview,**change)]))

    def test_changed_quantity_unit_kind_tax_price_base_or_discount_invalidates_the_old_proof(self):
        for key,value in [('quantity','3'),('unit','HUR'),('kind','labor'),('tax_rate','7'),
                          ('unit_price_net','99'),('cost_price_net','1'),('price_base_quantity','2'),
                          ('discount_percent','5')]:
            with self.subTest(field=key):
                preview=self.preview();draft=self.draft(positions=[self.adoption(preview)])
                position=deepcopy(draft['positions'][0]);position[key]=value
                updated=self.api.update(self.owner,draft['id'],request(revision=1,positions=[position]))
                self.assertNotIn('pricing_snapshot',updated['positions'][0])

    def test_unknown_costs_are_not_reported_as_zero_or_as_a_profit(self):
        article=self.api.save_article(self.owner,request(name='Unconfirmed cost',kind='material',unit='C62',unit_price_net='12'))
        draft=self.draft(positions=[dict(article_id=article['id'],article_revision=1,quantity='2')])
        value=self.api.document_calculation(self.owner,dict(revision=1),draft['id'])
        self.assertFalse(value['cost_summary']['complete']);self.assertIsNone(value['profit_net'])
        self.problem(409,lambda:self.preview(components=[dict(article_id=article['id'],article_revision=1,quantity='1')]))
        confirmed=self.api.save_article(self.owner,request(revision=1,cost_price_net='0'),article['id'])
        value=self.draft(positions=[dict(article_id=confirmed['id'],article_revision=2,quantity='1')])
        self.assertTrue(self.api.document_calculation(self.owner,dict(revision=1),value['id'])['cost_summary']['complete'])

    def test_pure_offer_preview_accepts_unknown_costs_and_validates_untrusted_snapshots(self):
        position=dict(description='Unknown cost',quantity='2',unit='C62',unit_price_net='10',tax_rate='19',cost_price_net=None)
        result=self.api.document_calculation(self.owner,request(project_id=self.project,positions=[position]))
        self.assertFalse(result['cost_summary']['complete']);self.assertIsNone(result['margin_percent'])
        self.problem(400,lambda:self.api.document_calculation(self.owner,request(project_id=self.project,
            positions=[{**position,'pricing_snapshot':{'unit_price_net':'NaN'}}])))

    def test_finance_scope_is_fresh_even_for_pure_preview_and_receipt_replay(self):
        actor=dict(id=self.office.add_user('accountant@example.test','Synthetic-password-123','accountant'),role='accountant')
        self.office.assign(self.owner,self.project,actor['id'])
        self.api.pricing_preview(actor,dict(project_id=self.project,base_cost_net='5'))
        self.problem(404,lambda:self.api.pricing_preview(actor,dict(project_id=self.other,base_cost_net='5')))
        self.office.assign(self.owner,self.project,actor['id'],remove=True)
        self.problem(404,lambda:self.api.pricing_preview(actor,dict(project_id=self.project,base_cost_net='5')))

    def test_missing_legacy_country_is_unknown_but_absent_legacy_input_keeps_default(self):
        draft=self.draft(buyer=None)
        self.assertEqual(draft['buyer']['country'],'')
        self.assertEqual(_buyer({'name':'Legacy absent country'})['country'],'DE')
        self.assertEqual(_buyer({'name':'Explicitly unknown country','country':''})['country'],'')

    def test_old_buyer_shape_without_contact_name_remains_valid_and_unchanged(self):
        draft=self.draft()
        self.assertNotIn('contact_name',draft['buyer'])
        self.api.save_settings(self.owner,request(revision=0,company_name='Synthetic seller',address_line='Test 1',
            postal_code='10115',city='Berlin',country='DE'))
        final=self.api.finalize(self.owner,draft['id'],render_prepared(self.api.prepare_finalization(self.owner,draft['id'],1)),uuid.uuid4().hex)
        row=self.office.db.execute('SELECT payload_json,payload_sha256 FROM business_documents WHERE id=?',(final['id'],)).fetchone()
        before=tuple(row);pdf=self.api.archive(self.owner,final['id'])
        validate_integrity(self.office)
        converted=self.api.convert(self.owner,final['id'],request(revision=final['revision'],target_kind='order_confirmation'))
        self.assertEqual(converted['buyer'],draft['buyer'])
        self.assertNotIn('contact_name',converted['buyer'])
        self.assertEqual(tuple(self.office.db.execute('SELECT payload_json,payload_sha256 FROM business_documents WHERE id=?',(final['id'],)).fetchone()),before)
        self.assertEqual(self.api.archive(self.owner,final['id']),pdf)

    def test_new_signature_pdf_formats_human_timestamp_and_keeps_canonical_iso_and_original(self):
        from reportlab.platypus import SimpleDocTemplate
        self.api.save_settings(self.owner,request(revision=0,company_name='Synthetic seller',address_line='Test 1',
            postal_code='10115',city='Berlin',country='DE'))
        draft=self.draft();final=self.api.finalize(self.owner,draft['id'],
            render_prepared(self.api.prepare_finalization(self.owner,draft['id'],1)),uuid.uuid4().hex)
        original=self.api.archive(self.owner,final['id'])
        # Real ReportLab PDF with compression disabled only for text inspection.
        def uncompressed(*args,**kwargs):
            return SimpleDocTemplate(*args,**{**kwargs,'pageCompression':0})
        with patch('reportlab.platypus.SimpleDocTemplate',side_effect=uncompressed):
            signed=self.api.sign(self.owner,final['id'],request(revision=final['revision'],level='simple',confirmation=True,
                signer='Synthetic signer',strokes=[[[0.1,0.2],[0.9,0.3]]]))
        pdf=self.api.signed_pdf(self.owner,final['id'],signed['id'])
        self.assertIn(b'Zeitpunkt: 10.01.2030, 12:00:00 UTC',pdf)
        self.assertEqual(signed['signed_at'],'2030-01-10T12:00:00+00:00')
        self.assertEqual(self.api.archive(self.owner,final['id']),original)
        validate_integrity(self.office)


class MeasurementTests(PricingFixture,unittest.TestCase):
    def test_five_real_dimensions_keep_decimal_quantity_and_canonical_units(self):
        source=self.measurement(('m','m2','m3','h','piece'))
        body=self.transfer(source,lines=[dict(line_index=i,unit_price_net='25.50') for i in range(5)])
        changes=self.office.db.total_changes;preview=self.api.measurement_preview(self.owner,body)
        self.assertEqual(self.office.db.total_changes,changes)
        self.assertEqual([p['unit'] for p in preview['positions']],['MTR','MTK','MTQ','HUR','C62'])
        self.assertEqual([p['quantity'] for p in preview['positions']],['6.8200']*5)
        self.assertEqual([p['net'] for p in preview['positions']],['173.91']*5)
        self.assertEqual(preview,self.api.measurement_preview(self.owner,body))

    def test_confirmed_transfer_freezes_source_and_survives_later_edit_and_final_offer(self):
        source=self.measurement();body=self.transfer(source);preview=self.api.measurement_preview(self.owner,body)
        transfer={**body,'preview_hash':preview['preview_hash'],'quantity_confirmation':True,'price_confirmation':True}
        draft=self.draft(positions=[],measurement_imports=[transfer]);position=draft['positions'][0]
        self.assertTrue(position['measurement_snapshot']['confirmed'])
        self.operations.save_entry(self.owner,self.project,'measurement',request(revision=source['revision'],title='Changed upstream',
            lines=[dict(description='Changed',unit='m2',formula='q',variables={'q':{'value':'99','unit':'m2'}})]),source['id'])
        self.api.save_settings(self.owner,request(revision=0,company_name='Synthetic seller',address_line='Test 1',
            postal_code='10115',city='Berlin',country='DE'))
        prepared=self.api.prepare_finalization(self.owner,draft['id'],1)
        final=self.api.finalize(self.owner,draft['id'],render_prepared(prepared),uuid.uuid4().hex)
        converted=self.api.convert(self.owner,final['id'],request(revision=final['revision'],target_kind='order_confirmation'))
        self.assertEqual(converted['positions'][0],position)
        validate_integrity(self.office)

    def test_preview_commit_race_unconfirmed_quantity_and_forged_provenance_are_rejected(self):
        source=self.measurement();body=self.transfer(source);preview=self.api.measurement_preview(self.owner,body)
        transfer={**body,'preview_hash':preview['preview_hash'],'quantity_confirmation':False,'price_confirmation':True}
        self.problem(400,lambda:self.draft(positions=[],measurement_imports=[transfer]))
        self.problem(400,lambda:self.draft(positions=preview['positions']))
        transfer['quantity_confirmation']=True
        self.operations.save_entry(self.owner,self.project,'measurement',request(revision=1,title='Changed',lines=source['lines']),source['id'])
        self.problem(409,lambda:self.draft(positions=[],measurement_imports=[transfer]))

    def test_measurement_project_and_dimension_are_not_inferred_or_crossed(self):
        source=self.measurement(('factor',))
        self.problem(415,lambda:self.api.measurement_preview(self.owner,self.transfer(source)))
        self.problem(404,lambda:self.api.measurement_preview(self.owner,self.transfer(source,project_id=self.other)))

    def test_frozen_provenance_cannot_describe_a_changed_quantity(self):
        source=self.measurement();body=self.transfer(source);preview=self.api.measurement_preview(self.owner,body)
        draft=self.draft(positions=[],measurement_imports=[{**body,'preview_hash':preview['preview_hash'],
            'quantity_confirmation':True,'price_confirmation':True}])
        position=deepcopy(draft['positions'][0]);position['quantity']='99'
        self.problem(400,lambda:self.api.update(self.owner,draft['id'],request(revision=1,positions=[position])))


class PricingHttpTests(unittest.TestCase):
    from online.test_plan_imports import PlanImportApiTests as _Fixture
    setUp=_Fixture.setUp
    tearDown=_Fixture.tearDown
    open_app=_Fixture.open_app
    call=_Fixture.call

    def test_authenticated_decimal_preview_and_measurement_adoption_http(self):
        ensure_schema(self.office,activate=True)
        prefix='/business';project=self.project
        article=self.call('POST',prefix+'/articles',request(name='Synthetic material',unit='C62',kind='material',
            unit_price_net='8',cost_price_net='5')).json
        preview=self.call('POST',prefix+'/commercial/pricing/preview',request(project_id=project,base_cost_net='10',
            components=[dict(article_id=article['id'],article_revision=1,quantity='2')],markup_percent='20')).json
        self.assertEqual(preview['unit_price_net'],'24.00')
        position=dict(description='Calculated',quantity='1',pricing=preview['inputs'],pricing_hash=preview['preview_hash'],price_confirmation=True)
        draft=self.call('POST',prefix+'/documents',request(project_id=project,kind='offer',issue_date='2030-01-10',positions=[position])).json
        result=self.call('POST',prefix+'/documents/'+draft['id']+'/calculation',request(revision=1)).json
        self.assertEqual(result['profit_net'],'4.00')
        source=self.call('POST',prefix+'/measurements',request(project_id=project,title='Synthetic area',
            lines=[dict(description='Area',unit='m2',formula='a*b',variables={'a':{'value':'2.2','unit':'m'},'b':{'value':'3.1','unit':'m'}})]),status=201).json
        body=dict(project_id=project,measurement_id=source['id'],measurement_revision=source['revision'],measurement_hash=source['content_hash'],
            lines=[dict(line_index=0,unit_price_net='25.50')])
        preview=self.call('POST',prefix+'/commercial/measurement-preview',request(**body)).json
        draft=self.call('POST',prefix+'/documents',request(project_id=project,kind='offer',issue_date='2030-01-10',positions=[],
            measurement_imports=[{**body,'preview_hash':preview['preview_hash'],'quantity_confirmation':True,'price_confirmation':True}])).json
        self.assertEqual(draft['totals']['net'],'173.91')
        self.assertEqual(draft['positions'][0]['measurement_snapshot']['content_hash'],source['content_hash'])


if __name__=='__main__':unittest.main()
