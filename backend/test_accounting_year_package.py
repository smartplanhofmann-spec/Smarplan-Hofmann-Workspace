"""Actual frozen EÜR years and hostile archive copies; no tax formula mirrors."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid
import zipfile

from cryptography.fernet import Fernet
import test_business_accounting_euer as euer_fixture
from accounting_year_package_v1 import build, sha
from accounting_year_verify_v1 import verify
from core import Problem, canonical
from online.instance import bind
from online.storage import Storage


class YearPackageTests(unittest.TestCase):
    def test_separate_authenticated_archive_hash_is_mandatory_and_not_an_intrinsic_completeness_claim(self):
        export,_,_=self.year();raw,manifest=build(self.office,self.owner,export['id'])
        self.assertFalse(manifest['intrinsic_dependency_closure'])
        self.assertEqual(manifest['required_trust'],'separately_authenticated_archive_sha256')
        with self.assertRaisesRegex(ValueError,'Separately authenticated'):verify(raw)
        with self.assertRaisesRegex(ValueError,'trusted separate hash'):verify(raw,'0'*64)
        checked=verify(raw,sha(raw));self.assertTrue(checked['verified'])
        self.assertFalse(checked['intrinsic_dependency_closure'])
        self.assertEqual(checked['verification_basis'],'separately_authenticated_archive_sha256_and_structural_checks')

    def setUp(self):
        self.f=euer_fixture.EuerWorkflowTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.office,self.owner,self.api=self.f.office,self.f.owner,self.f.api
        self.temp=tempfile.TemporaryDirectory(prefix='synthetic-year-review-');self.addCleanup(self.temp.cleanup)
        self.key=Fernet.generate_key();self.instance=uuid.uuid4().hex
        storage=Storage(self.office,self.key,'year-review.example.test',config={'server':{'path':str(Path(self.temp.name).resolve(strict=True)/'company')}})
        bind(self.office,self.instance,'year-review.example.test',self.key,storage)

    def year(self):
        income=self.f.sale();sale=self.f.post('cash',self.f.cash_payload(income))
        receipt=self.f.incoming();self.f.post('input_vat',self.f.vat_payload(receipt))
        expense=self.f.payout(receipt);self.f.post('cash',self.f.cash_payload(expense,'materials'))
        corrected=self.f.cash_payload(income);corrected['lines'][0]['account']='4401'
        self.f.post('correct',dict(entry_id=sale['id'],operation='cash',payload=corrected))
        exported=self.f.post('export',{'year':2026})
        return exported,receipt,income

    @staticmethod
    def files(raw):
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            return {name:archive.read(name) for name in archive.namelist()}

    @staticmethod
    def changed(raw, callback, *, rehash=False):
        files=YearPackageTests.files(raw);callback(files)
        if rehash:
            manifest=json.loads(files['manifest.json'])
            manifest['files']=[dict(path=key,sha256=sha(value),size=len(value)) for key,value in sorted(files.items()) if key!='manifest.json']
            files['manifest.json']=canonical(manifest).encode()
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_STORED) as archive:
            for name,value in sorted(files.items()):archive.writestr(name,value)
        return stream.getvalue()

    def test_actual_purchase_sale_correction_originals_and_frozen_bytes(self):
        exported,receipt,income=self.year();raw,manifest=build(self.office,self.owner,exported['id'])
        checked=verify(raw,sha(raw));self.assertTrue(checked['verified']);self.assertEqual(checked['originals'],2)
        files=self.files(raw);self.assertEqual(files['postings.csv'],exported['artifact']['csv'].encode())
        self.assertEqual(sha(files['report.json']),exported['artifact']['report_sha256'])
        journal=json.loads(files['journal.json']);self.assertEqual(len(journal['decisions']),5)
        self.assertTrue(any(v['entry']['operation']=='correct' for v in journal['decisions']))
        self.f.post('external_cash',self.f.external_payload(self.f.incoming('9.50','0.00','9.50')))
        self.assertEqual(build(self.office,self.owner,exported['id'])[0],raw)
        self.assertEqual(self.api.exported(self.owner,exported['id'])['report'],exported['artifact']['report'])

    def test_truncated_correction_rehashed_source_and_missing_original_rejected(self):
        exported,unused,unused2=self.year();raw,unused=build(self.office,self.owner,exported['id'])
        def remove_origin(files):
            j=json.loads(files['journal.json']);j['decisions']=j['decisions'][1:];files['journal.json']=canonical(j).encode()
        def cross_source(files):
            p=json.loads(files['proofs.json']);node=next(v for v in p['nodes'] if v['kind']=='source')
            node['payload']['source_hash']='f'*64;node['payload_sha256']=sha(node['payload']);files['proofs.json']=canonical(p).encode()
        def missing(files):del files[next(key for key in files if key.startswith('originals/'))]
        def csv(files):files['postings.csv']=files['postings.csv'].replace(b'4401',b'4402')
        for change in (remove_origin,cross_source,missing,csv):
            with self.subTest(change=change.__name__),self.assertRaises(ValueError):verify((changed:=self.changed(raw,change,rehash=True)),sha(changed))

    def test_local_standard_library_checker_after_office_closed_and_external_hash(self):
        exported,unused,unused2=self.year();raw,unused=build(self.office,self.owner,exported['id'])
        files=self.files(raw);script=Path(self.temp.name)/'verify_year_package.py';script.write_bytes(files['verify_year_package.py'])
        archive=Path(self.temp.name)/'year.zip';archive.write_bytes(raw)
        self.office.db.close()
        result=subprocess.run([sys.executable,'-I',str(script),str(archive),'--sha256',sha(raw)],capture_output=True,text=True,cwd=self.temp.name)
        self.assertEqual(result.returncode,0,result.stderr);self.assertTrue(json.loads(result.stdout)['verified'])
        wrong=subprocess.run([sys.executable,'-I',str(script),str(archive),'--sha256','0'*64],capture_output=True,text=True,cwd=self.temp.name)
        self.assertNotEqual(wrong.returncode,0)

    def test_unknown_export_or_current_finance_right_denied(self):
        exported,unused,unused2=self.year()
        with self.assertRaises(Problem) as caught:build(self.office,self.f.fixture.tech,exported['id'])
        self.assertEqual(caught.exception.status,403)
        with self.assertRaises(Problem) as caught:build(self.office,self.owner,uuid.uuid4().hex)
        self.assertEqual(caught.exception.status,404)

    def test_archive_duplicate_and_traversal_path_rejected_without_extraction(self):
        exported,unused,unused2=self.year();raw,unused=build(self.office,self.owner,exported['id'])
        altered=self.changed(raw,lambda files:files.update({'../escaped.txt':b'never write'}),rehash=True)
        with self.assertRaises(ValueError):verify(altered,sha(altered))
        stream=io.BytesIO(raw)
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            with zipfile.ZipFile(stream,'a') as archive:archive.writestr('report.json',b'{}')
        with self.assertRaises(ValueError):verify(stream.getvalue(),sha(stream.getvalue()))
        self.assertFalse((Path(self.temp.name).parent/'escaped.txt').exists())

    def bind_other(self,office):
        key=Fernet.generate_key();instance=uuid.uuid4().hex
        storage=Storage(office,key,'year-review.example.test',config={'server':{'path':str(Path(self.temp.name)/instance)}})
        bind(office,instance,'year-review.example.test',key,storage)

    def test_historical_asset_and_old_supplier_have_originals_no_new_cash_or_vat(self):
        import test_business_accounting_open_items as old_fixture
        import test_business_accounting_asset_openings as asset_fixture
        f=old_fixture.OpeningItemWorkflow('runTest');f.setUp();self.addCleanup(f.doCleanups);self.bind_other(f.office)
        asset=asset_fixture.HistoricalAssetWorkflow('runTest')
        # Reuse only the scenario helper against this actual shared store.
        asset.f=f.f;asset.office=f.office;asset.owner=f.owner;asset.euer=f.euer
        from business_accounting_asset_openings import HistoricalAssets
        asset.api=HistoricalAssets(f.office,clock=lambda:f.f.now)
        item,_=f.save('item','supplier-a',f.item('supplier-a','payable',prior=True));payment,_=f.payment(item,'79.33');f.classify(payment)
        historical,_=asset.save();f.euer.post('opening_depreciation',asset.depreciation_payload(historical))
        export=f.euer.post('export',dict(year=2026))
        before=f.euer.api.report(f.owner,2026);raw,manifest=build(f.office,f.owner,export['id'])
        self.assertTrue(verify(raw,sha(raw))['verified']);self.assertEqual(len(manifest['originals']),5)
        self.assertEqual(before,f.euer.api.report(f.owner,2026));self.assertEqual(before['totals']['confirmed_input_vat'],'0.00')
        self.assertEqual(before['totals']['confirmed_expenses'],'1279.33')
        # Later actual reversal/void must not rewrite the old source selection.
        posted=f.euer.api._ledger()['active']['opening_item_cash:'+payment['entity_key']]
        f.euer.post('reverse',dict(entry_id=posted['id']));f.save('payment',payment['entity_key'],dict(payment['payload'],status='void'))
        self.assertEqual(build(f.office,f.owner,export['id'])[0],raw)

    def test_public_payroll_finance_only_has_no_private_originals(self):
        import test_business_payroll_cash as payroll_fixture
        f=payroll_fixture.PayrollCashTests('runTest');f.setUp();self.addCleanup(f.doCleanups)
        data,run,identity,paid=f.case();batch=f.import_cash(f.body(paid));f.post('payroll_cash',f.payload(batch));export=f.post('export',dict(year=2026))
        uid=f.office.add_user('year-finance@example.test','Synthetic-only-password-123','accountant');actor=dict(id=uid,role='owner')
        from business_foundation import BusinessFoundation
        for permission in ('accounting.read','finance.read'):
            BusinessFoundation(f.office).save_grant(f.owner,dict(request_id=uuid.uuid4().hex,user_id=uid,permission=permission,effect='allow',scope='*',revision=0))
        raw,manifest=build(f.office,actor,export['id']);self.assertEqual(manifest['originals'],[])
        self.assertEqual(verify(raw,sha(raw))['private_source_boundaries'],['payroll_cash'])
        joined=b'\n'.join(self.files(raw).values())
        for private in (f.f.employee['id'],paid['id'],identity['id'],data['file']['id'],'12345678903','Synthetic technician','SYN-WAGE-001','verified-payroll-profile.pdf'):
            self.assertNotIn(private.encode(),joined)

    def test_unbooked_report_reference_rechecks_project_rights(self):
        from business_foundation import BusinessFoundation
        receipt=self.f.incoming();export=self.f.post('export',dict(year=2026))
        uid=self.office.add_user('year-report-finance@example.test','Synthetic-only-password-123','accountant');actor=dict(id=uid,role='owner')
        for permission in ('accounting.read','finance.read'):
            BusinessFoundation(self.office).save_grant(self.owner,dict(request_id=uuid.uuid4().hex,user_id=uid,permission=permission,effect='allow',scope='*',revision=0))
        self.office.assign(self.owner,self.f.fixture.project,uid)
        build(self.office,actor,export['id'])
        foundation=BusinessFoundation(self.office)
        foundation.save_grant(self.owner,dict(request_id=uuid.uuid4().hex,user_id=uid,permission='finance.read',effect='deny',scope=self.f.fixture.project,revision=0))
        with self.assertRaises(Problem) as caught:build(self.office,actor,export['id'])
        self.assertEqual(caught.exception.status,403)

    def test_independently_reported_removed_document_subgraph_is_rejected(self):
        income=self.f.sale();self.f.post('cash',self.f.cash_payload(income));export=self.f.post('export',dict(year=2026))
        raw,manifest=build(self.office,self.owner,export['id']);self.assertEqual(len(manifest['originals']),1)
        def remove_original_subgraph(files):
            proofs=json.loads(files['proofs.json']);removed={n['id'] for n in proofs['nodes'] if n['kind']=='document'}
            proofs['nodes']=[n for n in proofs['nodes'] if n['id'] not in removed]
            for node in proofs['nodes']:node['links']=[v for v in node['links'] if v not in removed]
            files['proofs.json']=canonical(proofs).encode()
            manifest=json.loads(files['manifest.json']);manifest['originals']=[];files['manifest.json']=canonical(manifest).encode()
            for name in list(files):
                if name.startswith('originals/'):del files[name]
        with self.assertRaises(ValueError):verify((changed:=self.changed(raw,remove_original_subgraph,rehash=True)),sha(changed))

    def test_later_receipt_review_profile_and_unrelated_project_do_not_change_old_bytes(self):
        exported,receipt,unused=self.year();raw,unused=build(self.office,self.owner,exported['id'])
        self.f.fixture.finance.review_receipt(self.owner,receipt['id'],self.f.fixture.review_body(revision=2,net='60.00',tax='11.40',gross='71.40'))
        self.f.configure(vat_effective_from='2025-01-01')
        project=self.office.add_project(self.owner,'Unrelated private annual project','Hidden customer')
        document=self.f.fixture.invoice(project=project)
        current=build(self.office,self.owner,exported['id'])[0];self.assertEqual(current,raw)
        joined=b'\n'.join(self.files(current).values())
        for value in (project,document['id'],'Unrelated private annual project','Hidden customer'):self.assertNotIn(value.encode(),joined)

    def test_cross_year_ten_day_correction_contains_its_other_year_origin(self):
        receipt=self.f.incoming('9.50','0.00','9.50',day='2026-12-31')
        payload=self.f.external_payload(receipt,day='2027-01-08');original=self.f.post('external_cash',payload)
        payload.update(euer_date='2026-12-31',year_rule=dict(kind='ten_day',economic_year=2026,due_date='2027-01-10',recurring=True))
        correction=self.f.post('correct',dict(entry_id=original['id'],operation='external_cash',payload=payload))
        exported=self.f.post('export',dict(year=2026));raw,unused=build(self.office,self.owner,exported['id'])
        decisions=json.loads(self.files(raw)['journal.json'])['decisions']
        self.assertEqual([row['entry']['id'] for row in decisions],[original['id'],correction['id'],exported['id']])
        self.assertTrue(verify(raw,sha(raw))['verified'])

    def test_unknown_financial_kind_is_explicitly_blocked(self):
        from accounting_year_package_v1 import Collector
        with self.assertRaises(Problem) as caught:Collector(self.office,self.owner).source(dict(kind='future_unknown_financial_source'))
        self.assertEqual(caught.exception.status,409)

    def test_later_prepayment_components_never_enter_earlier_vat_export(self):
        receipt=self.f.incoming()
        event=self.f.fixture.api.payout(self.owner,self.f.fixture.payout_body(receipt,amount='59.50',cash_date='2026-11-02'))
        payload=self.f.vat_payload(receipt,day='2026-11-02')
        payload.update(prepayment=True,payment_event_id=event['id'],service_date=None)
        self.f.post('input_vat',payload);export=self.f.post('export',dict(year=2026))
        raw,unused=build(self.office,self.owner,export['id'])
        self.f.documented(event);self.f.post('cash',self.f.cash_payload(event,'materials'))
        self.assertEqual(build(self.office,self.owner,export['id'])[0],raw)

    def test_actual_public_travel_has_no_private_trip_or_employee_originals(self):
        import test_business_travel_finance as travel_fixture
        f=travel_fixture.TravelFinanceTests('runTest');f.setUp();self.addCleanup(f.doCleanups)
        payment,command=f.paid();f.post('travel_cash',f.payload(payment));export=f.post('export',dict(year=2026))
        raw,manifest=build(f.office,f.owner,export['id'])
        self.assertEqual(manifest['originals'],[]);self.assertEqual(verify(raw,sha(raw))['private_source_boundaries'],['travel_cash'])
        joined=b'\n'.join(self.files(raw).values())
        for secret in (f.f.employee['id'],f.f.employee['name'],f.settlement['id'],command['reference_file_id'],f.f.place['id'],'Actual customer visit'):
            self.assertNotIn(secret.encode(),joined)

    def test_existing_c1_c2_r1_r2_mixed_actual_refunds_have_closed_originals(self):
        self.f.test_original_reused_and_mixed_refund_cents_flow_unchanged_into_tax_journal()
        self.bind_other(self.f.office)
        export=self.f.post('export',dict(year=2026))
        raw,manifest=build(self.f.office,self.f.owner,export['id'])
        self.assertTrue(verify(raw,sha(raw))['verified']);self.assertEqual(len(manifest['originals']),1)
        nodes=json.loads(self.files(raw)['proofs.json'])['nodes']
        self.assertEqual({row['id'].split(':')[1] for row in nodes if row['kind']=='documentary_component'},{'c1','c2','r1','r2'})

    def test_bounded_collection_fails_before_partial_output_without_database_writes(self):
        from unittest.mock import patch
        exported,unused,unused2=self.year();before=self.office.db.total_changes
        with patch('accounting_year_package_v1.MAX_BYTES',2048),self.assertRaises(Problem) as caught:
            build(self.office,self.owner,exported['id'])
        self.assertEqual(caught.exception.status,413);self.assertEqual(self.office.db.total_changes,before)


if __name__=='__main__':unittest.main()
