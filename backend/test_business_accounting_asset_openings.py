"""Accepted historical originals, immutable carryover and real EÜR follow-up."""
import base64
from copy import deepcopy
from datetime import date,timedelta
import json
import unittest
from unittest.mock import patch
import uuid

import business_schema
from core import Problem
from business_accounting_asset_openings import HistoricalAssets,INPUT,TABLES,public_source,validate_integrity
import test_business_accounting_openings as opening_fixture
import test_accounting_asset_opening_rules as rule_fixture


class HistoricalAssetWorkflow(unittest.TestCase):
    def setUp(self):
        self.f=opening_fixture.OpeningWorkflow('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.office=self.f.office;self.owner=self.f.owner;self.euer=self.f.fixture
        self.api=HistoricalAssets(self.office,clock=lambda:self.f.now)

    def original(self,key='m-001',marker='Original machine and complete historical depreciation register'):
        raw=('%PDF-1.4\nSynthetic '+marker+'\n%%EOF').encode()
        command=dict(request_id=uuid.uuid4().hex,asset_key=key,filename='synthetic-old-asset.pdf',media_type='application/pdf',content_base64=base64.b64encode(raw).decode())
        return self.api.upload_original(self.owner,command),command,raw

    def body(self,*,key='m-001',asset=None,position='Asset register row1',original=None,**changes):
        original=original or self.original(key)[0];state=self.api.state(self.owner);day=state['profile']['profile']['bookkeeping_start']
        return dict(expected_revision=state['revision'],state_hash=state['state_hash'],asset_key=key,profile_ref=state['profile_ref'],status='active',opening_date=day,
                    asset=asset or rule_fixture.asset(inventory_number=key),reason='Synthetic full original acquisition and earlier depreciation reviewed',
                    source=dict(original_id=original['id'],sha256=original['sha256'],position=position,history_through=(date.fromisoformat(day)-timedelta(days=1)).isoformat()))|changes

    def command(self,body):
        preview=self.api.preview(self.owner,body)
        return dict(body,request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash'])

    def save(self,**changes):
        command=self.command(self.body(**changes));return self.api.confirm(self.owner,command),command

    def depreciation_payload(self,entry,year=2026):
        source=public_source(self.office,entry['id'])
        return dict(asset_entry_id=entry['id'],source_hash=source['source_hash'],year=year,account='6220')

    def reject(self,status,call,*args):
        with self.assertRaises(Problem) as caught:call(*args)
        self.assertEqual(caught.exception.status,status,caught.exception.message);return caught.exception

    def test_real_original_carryover_then_exact_afa_without_new_cash_vat_or_changed_old_export(self):
        before=self.euer.api.report(self.owner,2026);export=self.euer.post('export',dict(year=2026));artifact=self.euer.api.exported(self.owner,export['id'])
        counts={table:self.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in ('business_accounting_cash_events','business_incoming_receipts','business_payments')}
        entry,command=self.save();report=self.euer.api.report(self.owner,2026)
        self.assertEqual(report['totals']['confirmed_expenses'],before['totals']['confirmed_expenses'])
        self.assertEqual(report['historical_assets'][0]['asset']['opening_book_value'],'1200.00')
        self.assertIn('historical_asset_depreciation_missing',[value['code'] for value in report['issues']])
        posted=self.euer.post('opening_depreciation',self.depreciation_payload(entry))
        report=self.euer.api.report(self.owner,2026)
        self.assertEqual(report['totals']['confirmed_expenses'],'1200.00');self.assertEqual(report['totals']['confirmed_input_vat'],'0.00')
        self.assertEqual(posted['effect']['details']['closing_book_value'],'0.00')
        self.assertEqual(report['cash_movements'],before['cash_movements'])
        self.assertEqual(counts,{table:self.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0] for table in counts})
        self.assertEqual(self.euer.api.exported(self.owner,export['id']),artifact)
        self.assertEqual(self.api.confirm(self.owner,command),entry)
        self.assertTrue(validate_integrity(self.office));self.assertTrue(business_schema.validate_integrity(self.office))

    def test_under_year_cutover_subtracts_actual_already_booked_year_amount(self):
        self.euer.configure(bookkeeping_start='2026-07-17')
        entry,_=self.save(asset=rule_fixture.asset(depreciation_in_start_year='500.00',opening_book_value='700.00'))
        posted=self.euer.post('opening_depreciation',self.depreciation_payload(entry))
        self.assertEqual(posted['effect']['details']['amount'],'700.00')
        self.assertEqual(posted['effect']['details']['imported_current_year_depreciation'],'500.00')
        self.assertEqual(self.euer.api.report(self.owner,2026)['totals']['confirmed_expenses'],'700.00')

    def test_same_original_position_cannot_be_doubled_by_renaming_inventory(self):
        first,_=self.save();other=self.original('m-002')[0]
        self.assertEqual(other['sha256'],first['source']['sha256'])
        self.reject(409,self.api.preview,self.owner,self.body(key='m-002',original=other,position=' Ａsset register row1 '))
        second,_=self.save(key='m-002',original=other,position='Asset register row2')
        self.assertEqual(len(self.api.state(self.owner)['items']),2);self.assertNotEqual(first['id'],second['id'])

    def test_active_follow_up_requires_counterposting_before_source_correction(self):
        entry,original_command=self.save();posted=self.euer.post('opening_depreciation',self.depreciation_payload(entry))
        self.reject(409,self.api.preview,self.owner,self.body(reason='Synthetic corrected description'))
        self.euer.post('reverse',dict(entry_id=posted['id']))
        revised,_=self.save(reason='Synthetic corrected description')
        self.assertEqual(revised['revision'],2);self.assertEqual(self.api.confirm(self.owner,original_command),entry)
        self.reject(409,self.euer.api.preview,self.owner,self.euer.body('opening_depreciation',self.depreciation_payload(entry)))
        self.euer.post('opening_depreciation',self.depreciation_payload(revised))
        self.assertEqual(self.euer.api.report(self.owner,2026)['totals']['confirmed_expenses'],'1200.00')
        self.assertTrue(business_schema.validate_integrity(self.office))

    def test_completed_asset_and_explicit_zero_year_need_no_fictitious_afa(self):
        old=rule_fixture.asset(acquired_on='2021-01-01',use_start='2021-01-01',depreciation_before_start_year='3600.00',opening_book_value='0.00')
        entry,_=self.save(asset=old)
        report=self.euer.api.report(self.owner,2026)
        self.assertFalse(any('depreciation_missing' in value['code'] for value in report['issues']))
        self.assertEqual(report['historical_assets'][0]['continuation']['amount'],'0.00')
        self.reject(409,self.euer.api.preview,self.owner,self.euer.body('opening_depreciation',self.depreciation_payload(entry)))

    def test_late_commit_failure_rolls_back_event_and_receipt(self):
        command=self.command(self.body())
        with patch.object(self.office,'audit',side_effect=RuntimeError('Synthetic interrupted asset acceptance')):
            with self.assertRaises(RuntimeError):self.api.confirm(self.owner,command)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM '+TABLES[1]).fetchone()[0],0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM '+TABLES[2]+" WHERE operation='confirm'").fetchone()[0],0)
        self.api.confirm(self.owner,command)


if __name__=='__main__':unittest.main()
