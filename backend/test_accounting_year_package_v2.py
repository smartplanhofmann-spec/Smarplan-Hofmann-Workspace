"""Actual accepted old-year sources; v1 archives remain byte-for-byte stable."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
from cryptography.fernet import Fernet
from core import Problem,canonical
from online.instance import bind
from online.storage import Storage
import test_accounting_year_openings as year_fixture
import test_accounting_year_package as v1_fixture
from accounting_year_package_v1 import build as build_v1,sha
from accounting_year_package_v2 import build,build_selected
from accounting_year_verify_v2 import verify


class YearPackageCarryover(unittest.TestCase):
    def setUp(self):
        self.f=year_fixture.YearOpeningWorkflow('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.office,self.owner=self.f.office,self.f.owner
        self.temp=tempfile.TemporaryDirectory(prefix='synthetic-year-package-v2-');self.addCleanup(self.temp.cleanup)
        key=Fernet.generate_key();storage=Storage(self.office,key,'year-package-v2.example.test',config={'server':{'path':self.temp.name}})
        bind(self.office,uuid.uuid4().hex,'year-package-v2.example.test',key,storage)

    def complete(self):
        entry,_=self.f.save();posted=self.f.classify(entry)
        payment,_=self.f.f.payment(self.f.old,'59.50',day='2026-11-01');self.f.f.classify(payment)
        export=self.f.f.euer.post('export',{'year':2026})
        return entry,posted,export

    def test_original_journal_and_old_item_chain_with_new_payment_have_no_new_cash(self):
        _,_,export=self.complete();before=self.office.db.total_changes
        raw,manifest=build_selected(self.office,self.owner,export['id']);checked=verify(raw,sha(raw))
        self.assertEqual(self.office.db.total_changes,before)
        self.assertEqual((checked['format'],checked['original_year_complete']),('smartplan-year-evidence-v2',True))
        files=v1_fixture.YearPackageTests.files(raw);report=json.loads(files['report.json'])
        self.assertEqual(report['totals']['confirmed_expenses'],'119.00')
        self.assertEqual(report['totals']['confirmed_input_vat'],'19.00')
        self.assertEqual([m['amount'] for m in report['cash_movements']],['59.50'])
        nodes=json.loads(files['proofs.json'])['nodes'];year=next(n['payload']['entry'] for n in nodes if n['kind']=='year_values')
        self.assertEqual([p['date'] for p in year['details']['historical_postings']],['2026-08-20','2026-08-20','2026-06-11'])
        self.assertEqual(year['details']['copied_rows'][1]['deducted_on'],'2026-07-10')
        self.assertEqual(manifest['originals'].__len__(),5)
        metadata=self.f.f.euer.api.year_evidence(self.owner,export['id'])
        self.assertEqual((metadata['format'],metadata['sha256'],metadata['size']),('smartplan-year-evidence-v2',sha(raw),len(raw)))

    def test_later_source_void_and_correction_preserve_earlier_v2_bytes(self):
        entry,command=self.f.save();posted=self.f.classify(entry);export=self.f.f.euer.post('export',{'year':2026})
        raw,_=build_selected(self.office,self.owner,export['id'])
        self.f.f.euer.post('reverse',{'entry_id':posted['id']});self.f.save(dict(self.f.payload,status='void'))
        payload=deepcopy(self.f.payload);payload['ledger_proof']=self.f.original('later independently corrected full journal')
        new,_=self.f.save(payload);self.f.classify(new)
        self.assertEqual(self.f.api.confirm(self.owner,command),entry)
        self.assertEqual(build_selected(self.office,self.owner,export['id'])[0],raw)
        later=self.f.f.euer.post('export',{'year':2026});later_raw,_=build_selected(self.office,self.owner,later['id'])
        self.assertTrue(verify(later_raw,sha(later_raw))['verified'])
        nodes=json.loads(v1_fixture.YearPackageTests.files(later_raw)['proofs.json'])['nodes']
        self.assertEqual(sorted(n['payload']['entry']['revision'] for n in nodes if n['kind']=='year_values'),[1,2,3])

    def test_partial_prior_coverage_stays_incomplete_and_unclassified_source_is_explicit(self):
        pending=self.f.f.euer.post('export',{'year':2026});raw,_=build_selected(self.office,self.owner,pending['id'])
        self.assertFalse(verify(raw,sha(raw))['original_year_complete'])
        payload=deepcopy(self.f.payload);payload['coverage']={'from':'2026-08-01','through':'2026-10-31'};payload['controls']=payload['controls'][:2]
        entry,_=self.f.save(payload);self.f.classify(entry);export=self.f.f.euer.post('export',{'year':2026})
        raw,_=build_selected(self.office,self.owner,export['id']);report=json.loads(v1_fixture.YearPackageTests.files(raw)['report.json'])
        self.assertFalse(verify(raw,sha(raw))['original_year_complete']);self.assertIsNone(report['totals']['euer_surplus'])
        self.assertEqual(report['totals']['confirmed_input_vat'],'0.00')

    def test_closed_trade_originals_and_original_acceptance_are_bound(self):
        payload=deepcopy(self.f.payload);record=deepcopy(self.f.old['payload'])
        record.update(external_id='closed-original',counterparty_key='other-supplier',invoice_number='CLOSED-1')
        record['invoice_proof']=self.f.original('closed supplier original');record['cutover_proof']=self.f.original('closed paid proof')
        record['prior_input_vat']['proof']=self.f.original('closed already deducted VAT')
        record['prior_payments'][0].update(gross='119.00',net='100.00',tax='19.00',proof=record['cutover_proof'])
        payload['sources'].append(dict(kind='closed_trade',record=record,accounts=self.f.rules.source['accounts'],cash_entry_keys=['CLOSED-CASH-1'],vat_entry_key='CLOSED-VAT-1'))
        for row,amount in zip(payload['controls'],('-150.00','-28.50','-38.00')):row['amount']=amount
        entry,_=self.f.save(payload);self.f.classify(entry);export=self.f.f.euer.post('export',{'year':2026})
        raw,_=build_selected(self.office,self.owner,export['id']);self.assertTrue(verify(raw,sha(raw))['verified'])
        def change(files):
            proofs=json.loads(files['proofs.json']);node=next(n for n in proofs['nodes'] if n['kind']=='year_values')
            node['payload']['acceptance']['request_id']=uuid.uuid4().hex;node['payload_sha256']=sha(node['payload'])
            files['proofs.json']=canonical(proofs).encode()
        with self.assertRaises(ValueError):verify((changed:=v1_fixture.YearPackageTests.changed(raw,change,rehash=True)),sha(changed))

    def test_rehashed_removed_original_subgraphs_and_coverage_are_rejected(self):
        _,_,export=self.complete();raw,_=build_selected(self.office,self.owner,export['id'])
        def remove_item(files):
            proofs=json.loads(files['proofs.json']);gone={n['id'] for n in proofs['nodes'] if n['kind']=='opening_item'}
            proofs['nodes']=[n for n in proofs['nodes'] if n['id'] not in gone]
            for n in proofs['nodes']:n['links']=[k for k in n['links'] if k not in gone]
            files['proofs.json']=canonical(proofs).encode()
        def remove_journal(files):
            proofs=json.loads(files['proofs.json']);node=next(n for n in proofs['nodes'] if n['kind']=='year_values')
            path='originals/'+node['payload']['entry']['payload']['ledger_proof']['sha256']+'.bin'
            for n in proofs['nodes']:n['originals']=[p for p in n['originals'] if p!=path]
            files['proofs.json']=canonical(proofs).encode();files.pop(path)
            manifest=json.loads(files['manifest.json']);manifest['originals']=[r for r in manifest['originals'] if r['path']!=path];files['manifest.json']=canonical(manifest).encode()
        for mutate in (remove_item,remove_journal):
            with self.subTest(mutate=mutate.__name__),self.assertRaises(ValueError):verify((changed:=v1_fixture.YearPackageTests.changed(raw,mutate,rehash=True)),sha(changed))

    def test_standalone_checker_and_fresh_rights(self):
        _,_,export=self.complete();raw,_=build_selected(self.office,self.owner,export['id']);files=v1_fixture.YearPackageTests.files(raw)
        path=Path(self.temp.name);(path/'verify.py').write_bytes(files['verify_year_package.py']);(path/'year.zip').write_bytes(raw)
        result=subprocess.run([sys.executable,'-I',str(path/'verify.py'),str(path/'year.zip'),'--sha256',sha(raw)],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertTrue(json.loads(result.stdout)['verified'])
        with self.assertRaises(Problem) as denied:build_selected(self.office,self.f.f.euer.fixture.tech,export['id'])
        self.assertEqual(denied.exception.status,403)

    def test_v1_selection_stays_byte_identical_after_later_year_original_upload(self):
        other=v1_fixture.YearPackageTests('runTest');other.setUp();self.addCleanup(other.doCleanups)
        export,_,_=other.year();before=build_v1(other.office,other.owner,export['id'])
        from business_accounting_year_openings import YearValues
        YearValues(other.office).upload_original(other.owner,dict(request_id=uuid.uuid4().hex,entity_key='2026',filename='later.pdf',media_type='application/pdf',content_base64=base64.b64encode(b'%PDF-1.4\nSynthetic later independent journal\n%%EOF').decode()))
        self.assertEqual(build_selected(other.office,other.owner,export['id']),before)
        self.assertEqual(other.api.year_evidence(other.owner,export['id'])['format'],'smartplan-year-evidence-v1')

if __name__=='__main__':unittest.main()
