"""Exact additive v15/v16 scope, real historical receipts and portable originals."""
import base64
from copy import deepcopy
import io
import sqlite3
import unittest
from unittest.mock import patch
import uuid
import zipfile
import business_api
import business_schema
from core import canonical
from business_accounting_year_openings import YearValues,TABLES,schema_statements
from company_export_catalog import COLUMNS,policy
import test_accounting_openings_registration as fixture

MODULE='business_accounting_year_openings'

class YearValuesRegistration(unittest.TestCase):
    office=fixture.OpeningRegistrationTests.office

    def test_exact_new_scope_and_reject_omitted_boolean_extra_old_horizon(self):
        office=self.office();fixture.require_review(office);evidence=fixture.report(office)
        self.assertEqual((evidence['schema'],evidence['accounting_horizon']['schema_version']),(16,15))
        self.assertEqual(evidence['accounting_horizon']['year_values']['table_counts'],dict.fromkeys(TABLES,0))
        bads=[]
        for key in ('omitted','extra','boolean','negative','hash','old'):
            bad=deepcopy(evidence);scope=bad['accounting_horizon']['year_values']
            if key=='omitted':scope['table_counts'].pop(TABLES[0])
            elif key=='extra':scope['table_counts']['invented']=0
            elif key=='boolean':scope['table_counts'][TABLES[0]]=True
            elif key=='negative':scope['table_counts'][TABLES[0]]=-1
            elif key=='hash':scope['sha256']='bad'
            else:bad['schema']=15;bad['accounting_horizon'].pop('year_values');bad['accounting_horizon']['schema_version']=14
            bads.append(bad)
        before='\n'.join(office.db.iterdump())
        for bad in bads:
            with self.subTest(bad=bad['schema']),self.assertRaises(ValueError):business_schema.reconcile_local_financial_restore(office,bad,fixture.digest(bad),application_stopped=True)
            self.assertEqual('\n'.join(office.db.iterdump()),before)
        self.assertTrue(business_schema.reconcile_local_financial_restore(office,evidence,fixture.digest(evidence),application_stopped=True)['reconciled'])

    def test_actual_v15_old_acceptance_unchanged_after_additive_v16_install(self):
        oldregistry=tuple(spec for spec in business_schema.registry() if spec.name!=MODULE)
        with patch.object(business_schema,'registry',return_value=oldregistry):
            office=self.office();fixture.require_review(office);old=fixture.report(office)
            self.assertEqual(old['schema'],15)
            accepted=business_schema.reconcile_local_financial_restore(office,old,fixture.digest(old),application_stopped=True)
            oldhorizon=canonical(business_schema.financial_accounting_horizon(office))
        business_schema.ensure_schema(office);business_schema.ensure_schema(office)
        current=business_schema.financial_accounting_horizon(office);current.pop('year_values');current['schema_version']=14
        self.assertEqual(canonical(current),oldhorizon)
        self.assertEqual(business_schema.reconcile_local_financial_restore(office,old,fixture.digest(old),application_stopped=True),accepted)
        fixture.require_review(office);bad=old|dict(restore_id=business_schema.state(office)['restore_id'])
        with self.assertRaises(ValueError):business_schema.reconcile_local_financial_restore(office,bad,fixture.digest(bad),application_stopped=True)
        report=fixture.report(office);self.assertTrue(business_schema.reconcile_local_financial_restore(office,report,fixture.digest(report),application_stopped=True)['reconciled'])

    def test_catalog_original_bytes_and_explicit_strict_routes(self):
        db=sqlite3.connect(':memory:');self.addCleanup(db.close)
        for statement in schema_statements('BLOB'):db.execute(statement)
        for table in TABLES:
            self.assertEqual([row[1] for row in db.execute('PRAGMA table_info('+table+')')],COLUMNS[table].split(','))
            metadata=policy(table);self.assertEqual(metadata['category'],'financial');self.assertTrue(metadata['sensitive']);self.assertEqual(metadata['included'],not table.endswith('_requests'))
        import test_business_company_handover as handover
        from company_export_archive import verify
        f=handover.CompanyHandoverTests('runTest');f.setUp();self.addCleanup(f.doCleanups)
        raw=b'%PDF-1.4\nSynthetic prior invoice and historic settlement record\n%%EOF'
        original=YearValues(f.office).upload_original(f.owner,dict(request_id=uuid.uuid4().hex,entity_key='2026',filename='old.pdf',media_type='application/pdf',content_base64=base64.b64encode(raw).decode()))
        _,data,_=f.archive()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            rows=f.rows(archive,TABLES[0]);self.assertEqual(rows[0]['id'],original['id']);self.assertEqual(archive.read(rows[0]['original']['$file']),raw)
            self.assertNotIn('data/'+TABLES[2]+'.jsonl',archive.namelist())
        self.assertTrue(verify(data,instance_id=f.instance)['valid'])
        for suffix,method in (('','GET'),('/history','GET'),('/years/2026','GET'),('/originals/'+'a'*32,'GET'),('/originals','POST'),('/preview','POST'),('/confirm','POST')):
            path='/business/accounting/year-values'+suffix;self.assertEqual(business_api.methods(path),method);self.assertTrue(business_api.strict_workflow_path(path))

    def test_finance_module_disabled_and_offline_commands_remain_blocked(self):
        from business_organization import Organization,NEEDS,MODULES,command_module
        from core import Problem
        office=self.office();owner=dict(id=office.add_user('owner@example.test','Synthetic-password-123','owner'))
        base='/business/accounting/year-values'
        self.assertEqual(command_module('/accounting/year-values/confirm',MODULE),'finance')
        for suffix in ('/originals','/preview','/confirm'):
            with self.assertRaises(Problem) as denied:business_api.dispatch(office,owner,base+suffix,'POST',{},offline=True,offline_capabilities=['time_events'])
            self.assertEqual(denied.exception.status,403)
        Organization(office).save(owner,dict(request_id=uuid.uuid4().hex,revision=0,needs=dict(NEEDS),modules={key:dict(visible=None,enabled=key!='finance') for key in MODULES}))
        self.assertEqual(business_api.dispatch(office,owner,base,'GET',{})[1],200)
        self.assertFalse(YearValues(office).state(owner)['can_prepare'])
        with self.assertRaises(Problem) as denied:YearValues(office)._access(owner,True)
        self.assertEqual(denied.exception.status,423)
        for suffix in ('/originals','/preview','/confirm'):
            with self.assertRaises(Problem) as denied:business_api.dispatch(office,owner,base+suffix,'POST',{})
            self.assertEqual(denied.exception.status,423)

if __name__=='__main__':unittest.main()
