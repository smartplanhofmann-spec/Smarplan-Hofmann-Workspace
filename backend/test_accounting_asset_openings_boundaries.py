"""Actual original, replay, rights and closed-period boundaries for old assets."""
from copy import deepcopy
import json
import unittest
import uuid

import business_schema
from business_accounting_asset_openings import HistoricalAssets,TABLES,validate_integrity
from business_organization import Organization,NEEDS,MODULES
from core import canonical
import test_business_accounting_asset_openings as workflow
from test_accounting_openings_registration import require_review


class HistoricalAssetBoundaries(unittest.TestCase):
    def setUp(self):
        self.f=workflow.HistoricalAssetWorkflow('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.office=self.f.office;self.owner=self.f.owner;self.api=self.f.api;self.euer=self.f.euer

    def test_server_identity_never_returns_an_unusable_overlong_casefolded_key(self):
        before=self.office.db.total_changes
        self.f.reject(400,self.api.identity,self.owner,dict(inventory_number='ß'*51))
        identity=self.api.identity(self.owner,dict(inventory_number='ß'*50))
        self.assertEqual(identity['asset_key'],'ss'*50)
        original,upload,raw=self.f.original(identity['asset_key'])
        self.assertEqual(original['asset_key'],identity['asset_key'])
        self.assertEqual(self.api.upload_original(self.owner,upload),original)

    def test_current_finance_permissions_apply_to_original_and_replay_without_bank_permission(self):
        fixture=self.euer.fixture;actor=fixture.actor('technician')
        for name in ('accounting.read','finance.read','accounting.admin','accounting.prepare','finance.write'):
            fixture.grant(actor,name)
        fixture.grant(actor,'bank.read',effect='deny')
        self.f.owner=actor
        entry,command=self.f.save();original=entry['source']['original_id']
        self.assertEqual(self.api.state(actor)['items'][0]['id'],entry['id'])
        self.assertEqual(self.api.confirm(actor,command),entry)
        fixture.grant(actor,'finance.read',effect='deny',revision=1)
        for call,args in ((self.api.state,(actor,)),(self.api.original,(actor,original)),
                          (self.api.history,(actor,'m-001')),(self.api.confirm,(actor,command))):
            with self.subTest(call=call.__name__):self.f.reject(403,call,*args)

    def test_exact_original_and_confirm_replay_do_not_duplicate_rows_changed_nonce_body_is_rejected(self):
        original,upload,raw=self.f.original();body=self.f.body(original=original);command=self.f.command(body)
        entry=self.api.confirm(self.owner,command);before=self.office.db.total_changes
        self.assertEqual(self.api.upload_original(self.owner,upload),original)
        self.assertEqual(self.api.confirm(self.owner,command),entry)
        self.assertEqual(self.office.db.total_changes,before)
        self.f.reject(409,self.api.confirm,self.owner,command|dict(reason='Different original review'))
        self.f.reject(409,self.api.upload_original,self.owner,upload|dict(filename='changed.pdf'))
        self.assertEqual(self.office.db.total_changes,before)

    def test_original_foreign_key_hash_cutoff_and_unconfirmed_preview_fail_before_acceptance(self):
        own=self.f.original()[0];foreign=self.f.original('m-002')[0]
        body=self.f.body(original=own)
        for status,change in ((409,dict(original_id=foreign['id'])),(409,dict(sha256='0'*64)),
                              (400,dict(history_through='2025-12-30'))):
            self.f.reject(status,self.api.preview,self.owner,body|dict(source=body['source']|change))
        command=self.f.command(body)
        self.f.reject(400,self.api.confirm,self.owner,command|dict(confirmation=False))
        self.f.reject(409,self.api.confirm,self.owner,command|dict(preview_hash='0'*64))
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM '+TABLES[1]).fetchone()[0],0)

    def test_missing_accepted_original_receipt_blocks_live_state_source_and_old_confirm(self):
        entry,command=self.f.save()
        self.office.db.execute('DROP TRIGGER '+TABLES[2]+'_delete_guard')
        self.office.db.execute('DELETE FROM '+TABLES[2]+" WHERE operation='original'")
        for call,args in ((self.api.state,(self.owner,)),(self.api.original,(self.owner,entry['source']['original_id'])),
                          (self.api.confirm,(self.owner,command)),(self.euer.api.report,(self.owner,2026))):
            with self.subTest(call=call.__name__):self.f.reject(409,call,*args)
        with self.assertRaises(ValueError):validate_integrity(self.office)

    def test_changed_profile_requires_reconfirmation_but_original_accepted_receipt_is_unchanged(self):
        entry,command=self.f.save();self.euer.configure(bookkeeping_start='2026-02-01')
        self.assertEqual(self.api.confirm(self.owner,command),entry)
        self.f.reject(409,self.euer.api.preview,self.owner,self.euer.body('opening_depreciation',self.f.depreciation_payload(entry)))
        self.assertIn('historical_asset_profile_changed',[issue['code'] for issue in self.euer.api.report(self.owner,2026)['issues']])

    def test_actual_closed_period_blocks_new_source_and_reopen_allows_revision(self):
        entry,command=self.f.save()
        self.euer.post('period',dict(period='2026-01',action='close',expected_period_revision=0,
            attestation=dict(bank_reconciled=True,originals_complete=True,special_cases_reviewed=True)))
        self.f.reject(409,self.api.preview,self.owner,self.f.body())
        self.assertEqual(self.api.confirm(self.owner,command),entry)
        self.euer.post('period',dict(period='2026-01',action='reopen',expected_period_revision=1,
            attestation=dict(bank_reconciled=True,originals_complete=True,special_cases_reviewed=True)))
        revised,_=self.f.save();self.assertEqual(revised['revision'],2)
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_restore_and_finance_pause_block_new_and_accepted_mutations(self):
        entry,command=self.f.save();require_review(self.office)
        self.f.reject(409,self.api.confirm,self.owner,command)
        self.assertEqual(self.api.original(self.owner,entry['source']['original_id'])[1],'application/pdf')
        with self.office.db:self.office.db.execute('UPDATE business_restore_state SET financial_reconciliation_required=0 WHERE singleton=1')
        Organization(self.office).save(self.owner,dict(request_id=uuid.uuid4().hex,revision=0,needs=dict(NEEDS),
            modules={key:dict(visible=None,enabled=key!='finance') for key in MODULES}))
        self.f.reject(423,self.api.confirm,self.owner,command)
        self.assertEqual(self.api.state(self.owner)['items'][0]['id'],entry['id'])


if __name__=='__main__':unittest.main()
