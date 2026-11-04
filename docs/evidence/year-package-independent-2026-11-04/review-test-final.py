"""Independent actual-origin review of explicitly externally anchored V1.

The original intrinsic-closure review is retained in docs/evidence; this suite
checks the changed, explicitly narrower trust contract accepted by Root.
"""
from copy import deepcopy
import io
import json
import unittest
import zipfile

from accounting_year_package_v1 import build,sha
from accounting_year_verify_v1 import verify
from core import canonical
import test_accounting_year_package as fixture


class IndependentYearPackageReview(unittest.TestCase):
    def setUp(self):
        self.f=fixture.YearPackageTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.office=self.f.office;self.owner=self.f.owner

    @staticmethod
    def prune(files,*,decisions=(),nodes=()):
        journal=json.loads(files['journal.json']);proofs=json.loads(files['proofs.json']);manifest=json.loads(files['manifest.json'])
        journal['decisions']=[row for row in journal['decisions'] if row['entry']['id'] not in decisions]
        proofmap={row['id']:row for row in proofs['nodes'] if row['id'] not in nodes}
        for row in proofmap.values():row['links']=[key for key in row['links'] if key not in nodes]
        report=json.loads(files['report.json'])
        roots={'source:'+row['entry']['effect']['source']['source_hash'] for row in journal['decisions'] if row['entry']['effect']}
        roots.update('source:'+row['source']['source_hash'] for row in report.get('historical_assets',[]))
        seen=set();todo=list(roots)
        while todo:
            key=todo.pop()
            if key in seen:continue
            seen.add(key)
            if key in proofmap:todo.extend(proofmap[key]['links'])
        proofs['nodes']=[row for row in proofs['nodes'] if row['id'] in seen and row['id'] not in nodes]
        used={name for row in proofs['nodes'] for name in row['originals']}
        manifest['originals']=[row for row in manifest['originals'] if row['path'] in used]
        for name in list(files):
            if name.startswith('originals/') and name not in used:del files[name]
        files['journal.json']=canonical(journal).encode();files['proofs.json']=canonical(proofs).encode();files['manifest.json']=canonical(manifest).encode()

    def checked_mutation(self,raw,callback):
        before=self.f.files(raw);modified=self.f.changed(raw,callback,rehash=True);after=self.f.files(modified)
        self.assertEqual(before['report.json'],after['report.json']);self.assertEqual(before['postings.csv'],after['postings.csv'])
        self.assertEqual(json.loads(before['manifest.json'])['export_hash'],json.loads(after['manifest.json'])['export_hash'])
        export_before=json.loads(before['journal.json'])['decisions'][-1];export_after=json.loads(after['journal.json'])['decisions'][-1]
        self.assertEqual(export_before,export_after)
        return modified

    def test_prior_year_input_vat_decision_cannot_be_removed_from_current_payment_archive(self):
        f=self.f.f;f.configure(vat_effective_from='2025-01-01',bookkeeping_start='2025-01-01')
        receipt=f.incoming(day='2025-12-10');vat=f.post('input_vat',f.vat_payload(receipt,day='2025-12-10'))
        expense=f.payout(receipt,day='2026-02-15');f.post('cash',f.cash_payload(expense,'materials'))
        exported=f.post('export',dict(year=2026));raw,manifest=build(self.office,self.owner,exported['id'])
        self.assertTrue(verify(raw,sha(raw))['verified']);self.assertEqual(exported['artifact']['report']['totals']['confirmed_expenses'],'59.50')
        journal=json.loads(self.f.files(raw)['journal.json']);self.assertIn(vat['id'],[row['entry']['id'] for row in journal['decisions']])
        modified=self.checked_mutation(raw,lambda files:self.prune(files,decisions=[vat['id']]))
        with self.assertRaises(ValueError):verify(modified,sha(raw))
        # Even if an untrusted caller supplies its replacement hash, this
        # already supported direct structural dependency must still fail.
        with self.assertRaises(ValueError):verify(modified,sha(modified))

    def old_item_fixture(self):
        import test_business_accounting_open_items as old
        f=old.OpeningItemWorkflow('runTest');f.setUp();self.addCleanup(f.doCleanups);self.f.bind_other(f.office);return f

    def test_original_item_revision_cannot_be_removed_behind_unchanged_payment_revision(self):
        f=self.old_item_fixture();first,_=f.save('item','old-supplier',f.item('old-supplier','payable'))
        second,_=f.save('item','old-supplier',first['payload']);payment,_=f.payment(second);f.classify(payment)
        exported=f.euer.post('export',dict(year=2026));raw,manifest=build(f.office,f.owner,exported['id']);self.assertTrue(verify(raw,sha(raw))['verified'])
        modified=self.checked_mutation(raw,lambda files:self.prune(files,nodes=['opening_item:'+first['id']]))
        with self.assertRaises(ValueError):verify(modified,sha(raw))
        # Even if an untrusted caller supplies its replacement hash, this
        # already supported direct structural dependency must still fail.
        with self.assertRaises(ValueError):verify(modified,sha(modified))

    def test_prior_actual_payment_proof_cannot_be_removed_from_later_rest_cent_source(self):
        f=self.old_item_fixture();f.euer.configure(vat_effective_from='2024-01-01',bookkeeping_start='2025-01-01')
        payload=f.item('old-supplier','payable');payload.update(invoice_date='2024-11-10',service_date='2024-11-10',invoice_received_date='2024-11-11',history_through='2024-12-31')
        payload['prior_input_vat'].update(entitlement_date='2024-11-11',declared_period='2024-11',deducted_on='2024-12-10')
        item,_=f.save('item','old-supplier',payload);first,_=f.payment(item,'39.67',day='2025-12-20');f.classify(first)
        second,_=f.payment(item,'39.67',day='2026-02-15');f.classify(second)
        exported=f.euer.post('export',dict(year=2026));raw,manifest=build(f.office,f.owner,exported['id']);self.assertTrue(verify(raw,sha(raw))['verified'])
        self.assertEqual((second['details']['net'],second['details']['tax']),('33.33','6.34'))
        modified=self.checked_mutation(raw,lambda files:self.prune(files,nodes=['opening_item:'+first['id']]))
        self.assertLess(len(json.loads(self.f.files(modified)['manifest.json'])['originals']),len(manifest['originals']))
        with self.assertRaises(ValueError):verify(modified,sha(raw))
        # Even if an untrusted caller supplies its replacement hash, this
        # already supported direct structural dependency must still fail.
        with self.assertRaises(ValueError):verify(modified,sha(modified))

    def test_incremental_invoice_predecessor_original_cannot_disappear(self):
        import test_business_accounting_invoice_chain as chain
        f=chain.IncrementalInvoiceTests('runTest');f.setUp();self.addCleanup(f.doCleanups);self.f.bind_other(f.office)
        first,middle,last=f.chain();unused,event,unused2=f.f.income(last,'35.70')
        f.e.post('cash',f.e.cash_payload(event));export=f.e.post('export',dict(year=2026));raw,manifest=build(f.office,f.owner,export['id'])
        self.assertTrue(verify(raw,sha(raw))['verified']);self.assertEqual(len(manifest['originals']),3)
        modified=self.checked_mutation(raw,lambda files:self.prune(files,nodes=['document:'+first['id']]))
        with self.assertRaises(ValueError):verify(modified,sha(raw))
        # Even if an untrusted caller supplies its replacement hash, this
        # already supported direct structural dependency must still fail.
        with self.assertRaises(ValueError):verify(modified,sha(modified))

    def test_separate_project_denial_does_not_block_old_selected_year_but_current_source_denial_does(self):
        import uuid
        from business_foundation import BusinessFoundation
        f=self.f.f;export,unused,unused2=self.f.year();original,_=build(self.office,self.owner,export['id'])
        uid=self.office.add_user('review-reader@example.test','Synthetic-only-password-123','accountant');actor=dict(id=uid,role='owner')
        foundation=BusinessFoundation(self.office)
        for permission in ('accounting.read','finance.read'):foundation.save_grant(self.owner,dict(request_id=uuid.uuid4().hex,user_id=uid,permission=permission,effect='allow',scope='*',revision=0))
        self.office.assign(self.owner,f.fixture.project,uid)
        private=self.office.add_project(self.owner,'Independent hidden project','Independent hidden counterparty')
        foundation.save_grant(self.owner,dict(request_id=uuid.uuid4().hex,user_id=uid,permission='finance.read',effect='deny',scope=private,revision=0))
        hidden=f.fixture.invoice(project=private);self.assertEqual(build(self.office,actor,export['id'])[0],original)
        all_files=b'\n'.join(self.f.files(original).values())
        for secret in (private,hidden['id'],'Independent hidden project','Independent hidden counterparty'):self.assertNotIn(secret.encode(),all_files)
        foundation.save_grant(self.owner,dict(request_id=uuid.uuid4().hex,user_id=uid,permission='finance.read',effect='deny',scope=f.fixture.project,revision=0))
        from core import Problem
        with self.assertRaises(Problem) as denied:build(self.office,actor,export['id'])
        self.assertEqual(denied.exception.status,403)

    def test_source5_actual_separate_payments_export_only_financial_projection(self):
        import uuid
        import test_business_payroll_multiple as payroll
        from business_foundation import BusinessFoundation
        f=payroll.MultipleWorkflow('runTest');f.setUp();self.addCleanup(f.doCleanups)
        state=f.paid_upgrade(cash=True);finance=state['finance'];body=finance.body(state['payment']);body['sources'][0]['payment_indexes']=[1]
        last=finance.import_cash(body)
        for batch in (state['first'],last):finance.post('payroll_cash',finance.payload(batch))
        export=finance.post('export',dict(year=2026));office=f.f.office;owner=f.f.owner
        uid=office.add_user('source5-finance-only@example.test','Synthetic-only-password-123','accountant');actor=dict(id=uid,role='owner')
        foundation=BusinessFoundation(office)
        for permission in ('accounting.read','finance.read'):foundation.save_grant(owner,dict(request_id=uuid.uuid4().hex,user_id=uid,permission=permission,effect='allow',scope='*',revision=0))
        raw,manifest=build(office,actor,export['id']);checked=verify(raw,sha(raw));self.assertEqual(checked['private_source_boundaries'],['payroll_cash']);self.assertEqual(manifest['originals'],[])
        joined=b'\n'.join(self.f.files(raw).values())
        secrets=(f.f.employee['id'],f.f.employee['name'],state['run']['id'],state['old_payment']['id'],state['payment']['id'],f.source['components'][0]['component_key'],f.source['components'][0]['planned_receipts'][0]['event_key'],f.f.original['id'])
        for secret in secrets:self.assertNotIn(secret.encode(),joined)
        def inject(files):
            payload=b'Synthetic forbidden private employee original';name='originals/'+sha(payload)+'.bin';files[name]=payload
            proof=json.loads(files['proofs.json']);node=next(v for v in proof['nodes'] if v['kind']=='source');node['originals']=[name];files['proofs.json']=canonical(proof).encode()
            manifest=json.loads(files['manifest.json']);manifest['originals']=[dict(path=name,sha256=sha(payload),size=len(payload),descriptions=[])];files['manifest.json']=canonical(manifest).encode()
        modified=self.checked_mutation(raw,inject)
        for anchor in (sha(raw),sha(modified)):
            with self.subTest(anchor=anchor),self.assertRaises(ValueError):verify(modified,anchor)

    def test_cross_year_correction_requires_actual_other_year_origin_and_keeps_old_zip(self):
        f=self.f.f;receipt=f.incoming('9.50','0.00','9.50',day='2026-12-31')
        payload=f.external_payload(receipt,day='2027-01-08');origin=f.post('external_cash',payload)
        old=f.post('export',dict(year=2027));oldbytes,_=build(self.office,self.owner,old['id'])
        payload.update(euer_date='2026-12-31',year_rule=dict(kind='ten_day',economic_year=2026,due_date='2027-01-10',recurring=True))
        correction=f.post('correct',dict(entry_id=origin['id'],operation='external_cash',payload=payload));export=f.post('export',dict(year=2026))
        raw,_=build(self.office,self.owner,export['id']);self.assertTrue(verify(raw,sha(raw))['verified']);self.assertEqual(build(self.office,self.owner,old['id'])[0],oldbytes)
        modified=self.checked_mutation(raw,lambda files:self.prune(files,decisions=[origin['id']]))
        with self.assertRaises(ValueError):verify(modified,sha(raw))
        # Even if an untrusted caller supplies its replacement hash, this
        # already supported direct structural dependency must still fail.
        with self.assertRaises(ValueError):verify(modified,sha(modified))

    def test_archive_size_count_compression_and_forged_original_bytes_fail_without_output(self):
        from unittest.mock import patch
        from core import Problem
        export,unused,unused2=self.f.year();raw,_=build(self.office,self.owner,export['id']);before=self.office.db.total_changes
        files=self.f.files(raw)
        with patch('accounting_year_package_v1.MAX_FILES',len(files)-1),self.assertRaises(Problem) as denied:build(self.office,self.owner,export['id'])
        self.assertEqual(denied.exception.status,413);self.assertEqual(self.office.db.total_changes,before)
        with patch('accounting_year_verify_v1.MAX_FILES',len(files)-1),self.assertRaises(ValueError):verify(raw,sha(raw))
        with patch('accounting_year_verify_v1.MAX_BYTES',len(raw)-1),self.assertRaises(ValueError):verify(raw,sha(raw))
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            for key,value in files.items():archive.writestr(key,value)
        with self.assertRaises(ValueError):verify(stream.getvalue(),sha(raw))
        def replace_original(values):
            key=next(k for k in values if k.startswith('originals/'));values[key]=b'%PDF-1.4 Changed original without original hash change'
        modified=self.checked_mutation(raw,replace_original)
        for anchor in (sha(raw),sha(modified)):
            with self.subTest(anchor=anchor),self.assertRaises(ValueError):verify(modified,anchor)

    def test_prior_vat_cannot_be_hidden_by_relabeling_unverified_prefix_target_hint(self):
        f=self.f.f;f.configure(vat_effective_from='2025-01-01',bookkeeping_start='2025-01-01')
        receipt=f.incoming(day='2025-12-10');vat=f.post('input_vat',f.vat_payload(receipt,day='2025-12-10'))
        expense=f.payout(receipt,day='2026-02-15');f.post('cash',f.cash_payload(expense,'materials'))
        exported=f.post('export',dict(year=2026));raw,_=build(self.office,self.owner,exported['id'])
        def hide(files):
            self.prune(files,decisions=[vat['id']]);journal=json.loads(files['journal.json'])
            # The full original entry hash and export are unchanged. Only the
            # auxiliary target hint outside that original hash is relabeled.
            journal['prefix'][vat['sequence']-1]['target_hash']=sha('unrelated auxiliary target')
            files['journal.json']=canonical(journal).encode()
        modified=self.checked_mutation(raw,hide)
        with self.assertRaises(ValueError):verify(modified,sha(raw))

    def test_replaced_actual_payment_cannot_be_substituted_by_equal_voided_old_payment(self):
        f=self.old_item_fixture();f.euer.configure(vat_effective_from='2024-01-01',bookkeeping_start='2025-01-01')
        payload=f.item('old-supplier','payable');payload.update(invoice_date='2024-11-10',service_date='2024-11-10',invoice_received_date='2024-11-11',history_through='2024-12-31')
        payload['prior_input_vat'].update(entitlement_date='2024-11-11',declared_period='2024-11',deducted_on='2024-12-10')
        item,_=f.save('item','old-supplier',payload);mistaken,_=f.payment(item,'39.67',day='2025-12-19')
        void,_=f.save('payment',mistaken['entity_key'],dict(mistaken['payload'],status='void'))
        actual,_=f.payment(item,'39.67',day='2025-12-20');f.classify(actual)
        final,_=f.payment(item,'39.67',day='2026-02-15');f.classify(final)
        exported=f.euer.post('export',dict(year=2026));raw,manifest=build(f.office,f.owner,exported['id']);self.assertTrue(verify(raw,sha(raw))['verified'])
        modified=self.checked_mutation(raw,lambda files:self.prune(files,nodes=['opening_item:'+void['id'],'opening_item:'+actual['id']]))
        left=json.loads(self.f.files(modified)['proofs.json'])['nodes']
        self.assertTrue(any(n['id']=='opening_item:'+mistaken['id'] for n in left))
        self.assertFalse(any(n['id']=='opening_item:'+actual['id'] for n in left))
        with self.assertRaises(ValueError):verify(modified,sha(raw))

    def test_authenticated_original_hash_is_mandatory_and_scope_is_explicitly_limited(self):
        export,unused,unused2=self.f.year();raw,manifest=build(self.office,self.owner,export['id'])
        self.assertIs(manifest['intrinsic_dependency_closure'],False)
        self.assertEqual(manifest['required_trust'],'separately_authenticated_archive_sha256')
        for supplied in (None,'','0'*64,True):
            with self.subTest(supplied=supplied),self.assertRaises(ValueError):verify(raw,supplied)
        checked=verify(raw,sha(raw));self.assertTrue(checked['verified'])
        self.assertIs(checked['intrinsic_dependency_closure'],False)
        self.assertEqual(checked['verification_basis'],'separately_authenticated_archive_sha256_and_structural_checks')

    def test_a_replaced_untrusted_hash_does_not_prove_intrinsic_dependency_completeness(self):
        f=self.f.f;f.configure(vat_effective_from='2025-01-01',bookkeeping_start='2025-01-01')
        receipt=f.incoming(day='2025-12-10');vat=f.post('input_vat',f.vat_payload(receipt,day='2025-12-10'))
        expense=f.payout(receipt,day='2026-02-15');f.post('cash',f.cash_payload(expense,'materials'))
        exported=f.post('export',dict(year=2026));raw,_=build(self.office,self.owner,exported['id'])
        def hide(files):
            self.prune(files,decisions=[vat['id']]);journal=json.loads(files['journal.json'])
            journal['prefix'][vat['sequence']-1]['target_hash']=sha('unrelated untrusted auxiliary target')
            files['journal.json']=canonical(journal).encode()
        modified=self.checked_mutation(raw,hide)
        with self.assertRaises(ValueError):verify(modified,sha(raw))
        # Deliberately wrong trust input: a malicious sender supplies both its
        # modified archive and its own checksum. This cannot prove provenance.
        checked=verify(modified,sha(modified));self.assertTrue(checked['verified'])
        self.assertIs(checked['intrinsic_dependency_closure'],False)
        self.assertEqual(checked['verification_basis'],'separately_authenticated_archive_sha256_and_structural_checks')

if __name__=='__main__':unittest.main()
