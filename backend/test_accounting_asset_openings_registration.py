"""Additive historical assets, exact restore scope and protected company export."""
from copy import deepcopy
import base64
import io
import json
import sqlite3
import unittest
from unittest.mock import patch
import uuid
import zipfile

import business_api
import business_schema
from business_accounting_asset_openings import HistoricalAssets,TABLES,schema_statements
from company_export_catalog import COLUMNS,policy
from core import canonical
import test_accounting_openings_registration as fixture


MODULE='business_accounting_asset_openings'


class HistoricalAssetRegistration(unittest.TestCase):
    office=fixture.OpeningRegistrationTests.office

    def setUp(self):
        previous=tuple(spec for spec in business_schema.registry() if spec.name!='business_accounting_open_items')
        guard=patch.object(business_schema,'registry',return_value=previous);guard.start();self.addCleanup(guard.stop)

    def test_current_scope_requires_exact_assets_and_old_scope_cannot_unlock_new_restore(self):
        office=self.office();fixture.require_review(office);evidence=fixture.report(office)
        self.assertEqual(evidence['schema'],14);self.assertEqual(evidence['accounting_horizon']['schema_version'],13)
        scope=evidence['accounting_horizon']['historical_assets']
        self.assertEqual(scope['table_counts'],dict.fromkeys(TABLES,0))
        older=deepcopy(evidence);older['schema']=13;older['accounting_horizon'].pop('historical_assets');older['accounting_horizon']['schema_version']=12
        business_schema._validate_financial_accounting_horizon(older['accounting_horizon'],13)
        bads=[older]
        for case in ('omitted','extra','boolean','negative','schema','hash'):
            bad=deepcopy(evidence);value=bad['accounting_horizon']['historical_assets']
            if case=='omitted':value['table_counts'].pop(TABLES[0])
            elif case=='extra':value['table_counts']['future_table']=0
            elif case=='boolean':value['table_counts'][TABLES[0]]=True
            elif case=='negative':value['table_counts'][TABLES[0]]=-1
            elif case=='schema':value['schema_version']=True
            else:value['sha256']='bad'
            bads.append(bad)
        before='\n'.join(office.db.iterdump())
        for value in bads:
            with self.subTest(value=value['schema']),self.assertRaises(ValueError):
                business_schema.reconcile_local_financial_restore(office,value,fixture.digest(value),application_stopped=True)
            self.assertEqual('\n'.join(office.db.iterdump()),before)
        accepted=business_schema.reconcile_local_financial_restore(office,evidence,fixture.digest(evidence),application_stopped=True)
        self.assertTrue(accepted['reconciled'])
        self.assertEqual(business_schema.reconcile_local_financial_restore(office,evidence,fixture.digest(evidence),application_stopped=True),accepted)

    def test_actual_schema13_approval_survives_additive_migration_but_new_restore_requires14(self):
        registry=tuple(spec for spec in business_schema.registry() if spec.name!=MODULE)
        with patch.object(business_schema,'registry',return_value=registry):
            office=self.office('before-assets');fixture.require_review(office);old=fixture.report(office)
            self.assertEqual(old['schema'],13)
            accepted=business_schema.reconcile_local_financial_restore(office,old,fixture.digest(old),application_stopped=True)
            previous=canonical(business_schema.financial_accounting_horizon(office))
        business_schema.ensure_schema(office);business_schema.ensure_schema(office)
        new=business_schema.financial_accounting_horizon(office);new.pop('historical_assets');new['schema_version']=12
        self.assertEqual(canonical(new),previous)
        before='\n'.join(office.db.iterdump())
        self.assertEqual(business_schema.reconcile_local_financial_restore(office,old,fixture.digest(old),application_stopped=True),accepted)
        self.assertEqual('\n'.join(office.db.iterdump()),before)
        fixture.require_review(office);stale=old|dict(restore_id=business_schema.state(office)['restore_id'])
        with self.assertRaises(ValueError):business_schema.reconcile_local_financial_restore(office,stale,fixture.digest(stale),application_stopped=True)
        current=fixture.report(office)
        self.assertTrue(business_schema.reconcile_local_financial_restore(office,current,fixture.digest(current),application_stopped=True)['reconciled'])

    def test_exact_catalog_and_actual_archive_retain_original_without_technical_receipts(self):
        db=sqlite3.connect(':memory:');self.addCleanup(db.close)
        for statement in schema_statements('BLOB'):db.execute(statement)
        for table in TABLES:
            self.assertEqual([row[1] for row in db.execute('PRAGMA table_info('+table+')')],COLUMNS[table].split(','))
            metadata=policy(table);self.assertEqual(metadata['category'],'financial');self.assertTrue(metadata['sensitive'])
            self.assertEqual(metadata['included'],not table.endswith('_requests'))
            self.assertEqual(metadata['source_access'],'Current global accounting read and finance read access')
        import test_business_company_handover as handover
        from company_export_archive import verify
        f=handover.CompanyHandoverTests('runTest');f.setUp();self.addCleanup(f.doCleanups)
        raw=b'%PDF-1.4\nSynthetic original acquisition and complete historic depreciation\n%%EOF'
        original=HistoricalAssets(f.office).upload_original(f.owner,dict(request_id=uuid.uuid4().hex,asset_key='machine',filename='original.pdf',
            media_type='application/pdf',content_base64=base64.b64encode(raw).decode()))
        _,archive_bytes,_=f.archive()
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            rows=f.rows(archive,TABLES[0]);self.assertEqual(rows[0]['id'],original['id'])
            self.assertEqual(archive.read(rows[0]['original']['$file']),raw)
            self.assertNotIn('data/'+TABLES[2]+'.jsonl',archive.namelist())
        self.assertTrue(verify(archive_bytes,instance_id=f.instance)['valid'])

    def test_route_registration_offline_gates_and_incomplete_dependency(self):
        office=self.office();owner=dict(id=office.add_user('owner@example.test','Synthetic-password-123','owner'))
        base='/business/accounting/historical-assets'
        for suffix,method in (('','GET'),('/history','GET'),('/originals/'+'a'*32,'GET'),('/originals','POST'),('/preview','POST'),('/confirm','POST')):
            self.assertEqual(business_api.methods(base+suffix),method);self.assertTrue(business_api.strict_workflow_path(base+suffix))
            with self.assertRaises(fixture.Problem) as caught:business_api.dispatch(office,owner,base+suffix,method,{},offline=True,offline_capabilities=['time_events'])
            self.assertEqual(caught.exception.status,403)
        capabilities=business_api.dispatch(office,owner,'/business/capabilities','GET',{})[0]
        self.assertIn(MODULE,capabilities['capabilities']);self.assertIn('accounting_historical_assets',capabilities['features'])
        all_caps=business_schema.state(office)['read_capabilities']
        with patch.object(business_schema,'state',return_value=dict(read_capabilities=[value for value in all_caps if value!='business_accounting_openings'])):
            with self.assertRaises(ValueError):business_schema.financial_accounting_horizon(office)


if __name__=='__main__':unittest.main()
