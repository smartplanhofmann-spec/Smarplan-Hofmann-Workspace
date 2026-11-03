"""Incremental issued invoices through exact cash/components/refund/EÜR journals.

SQLite uses the existing explicitly synthetic invoice issuer. The separate PG
suite proves the production archive/role/transport/restore boundary.
"""
import hashlib
import json
import unittest
import uuid

import test_business_accounting_refunds_v2 as fixture
import test_business_accounting_euer as euer_fixture
from accounting_invoice_sources import archive_chain, groups_from_chain, eligibility
from business_accounting_euer import EuerAccounting, validate_integrity
from business_accounting_profile import AccountingPreparationProfile
from business_documents import render_prepared
from core import canonical


class IncrementalInvoiceTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.VersionedRefundDomainTests('runTest')
        self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.office = self.f.office; self.owner = self.f.owner
        self.e = euer_fixture.EuerWorkflowTests('runTest')
        self.e.fixture = self.f; self.e.office = self.office; self.e.owner = self.owner
        self.e.api = EuerAccounting(self.office, clock=self.f.clock)
        self.e.profile = AccountingPreparationProfile(self.office, clock=self.f.clock)
        self.e.configure()

    def issue(self, kind, net='100.00', previous=(), positions=None, project=None):
        draft = self.f.docs.create(self.owner, self.f.legacy_req(project_id=project or self.f.project,
            kind=kind, issue_date='2026-11-01', due_date='2026-11-10', previous_document_ids=list(previous),
            buyer=dict(name='Synthetic buyer', address_line='Buyer street', postal_code='10117', city='Berlin', country='DE'),
            positions=positions or [dict(description='Synthetic contract', quantity='1', unit='m', unit_price_net=net, tax_rate='19')]))
        return self.f.docs.finalize(self.owner, draft['id'], render_prepared(self.f.docs.prepare_finalization(
            self.owner, draft['id'], draft['revision'])), uuid.uuid4().hex)

    def chain(self):
        first = self.issue('advance_invoice', '30.00')
        middle = self.issue('cumulative_invoice', '70.00', [first['id']])
        last = self.issue('final_invoice', '100.00', [middle['id']])
        return first, middle, last

    def row(self, document):
        return self.office.db.execute('SELECT * FROM business_documents WHERE id=?', (document['id'],)).fetchone()

    def book_all_cash(self):
        for row in self.office.db.execute('SELECT id FROM business_accounting_cash_events ORDER BY sequence').fetchall():
            event = self.f.api.event(self.owner, row['id'])
            self.e.post('cash', self.e.cash_payload(event))
        report = self.e.api.report(self.owner, 2026)
        self.assertTrue(report['complete_for_recorded_sources'], report['issues'])
        self.assertTrue(validate_integrity(self.office))
        return report

    def test_advance_and_final_add_only_incremental_contract_cents_to_euer(self):
        first = self.issue('advance_invoice', '50.00')
        last = self.issue('final_invoice', '100.00', [first['id']])
        for document in (first, last):
            self.f.income(document, '59.50')
        report = self.book_all_cash()
        self.assertEqual(report['totals']['confirmed_income'], '119.00')
        self.assertEqual(report['totals']['confirmed_output_vat'], '19.00')
        self.assertEqual(report['totals']['euer_surplus'], '119.00')
        self.assertEqual(json.loads(self.row(last)['payload_json'])['contract_totals']['gross'], '119.00')
        self.assertEqual(groups_from_chain(archive_chain(self.office, self.row(last)))[0]['gross'], '59.50')

    def test_three_stage_chain_partial_payments_round_without_duplicating_ancestors(self):
        first, middle, last = self.chain()
        for document, amounts in ((first, ('11.90','11.90','11.90')),
                                   (middle, ('15.87','15.87','15.86')),
                                   (last, ('11.90','11.90','11.90'))):
            entries = [self.f.income(document, amount)[2] for amount in amounts]
            expected = '40.00' if document is middle else '30.00'
            self.assertEqual(sum(int(value['net'].replace('.','')) for value in entries), int(expected.replace('.','')))
        proof = archive_chain(self.office, self.row(last))
        self.assertEqual(len(proof['nodes']), 3)
        self.assertEqual(json.loads(self.row(last)['payload_json'])['previous_issued_gross'], '83.30')
        report = self.book_all_cash()
        self.assertEqual((report['totals']['confirmed_income'], report['totals']['confirmed_output_vat']), ('119.00','19.00'))

    def test_mixed_tax_groups_rest_cents_and_overpayment_are_exact(self):
        def positions(a,b):
            return [dict(description='Standard',quantity='1',unit='m',unit_price_net=a,tax_rate='19'),
                    dict(description='Reduced',quantity='1',unit='m',unit_price_net=b,tax_rate='7')]
        first = self.issue('advance_invoice', positions=positions('30.00','20.00'))
        last = self.issue('final_invoice', previous=[first['id']], positions=positions('100.00','50.00'))
        for document, parts in ((first, [('11.90','7.14'),('11.90','7.13'),('11.90','7.13')]),
                                (last, [('27.77','10.70'),('27.77','10.70'),('27.76','10.70')])):
            for standard,reduced in parts:
                amount = f'{(int(standard.replace(".",""))+int(reduced.replace(".","")))/100:.2f}'
                _, event = self.f.cash_event(document, amount)
                groups = {g['rate']:g for g in self.f.components.portions(self.owner,event['id'])['items'][0]['groups']}
                selected = [dict(group_id=groups[rate]['group_id'],amount=value) for rate,value in (('19',standard),('7',reduced))]
                self.f.components.confirm(self.owner,event['id'],self.f.component_confirm_body(event,groups=selected))
        report = self.book_all_cash()
        self.assertEqual((report['totals']['confirmed_income'],report['totals']['confirmed_output_vat']),('172.50','22.50'))
        # Real bank overpayments may be recorded, but never become another
        # taxable document cent or reusable component without a real origin.
        _,excess = self.f.cash_event(last,'0.01')
        self.assertEqual(self.f.components.state(self.owner,excess['id'])['blocked_reason'],'group_capacity_exceeded')
        other = self.issue('advance_invoice', '200.00')
        self.f.problem(409,self.issue,'final_invoice','100.00',[other['id']])

    def test_late_payment_assignment_adds_no_cash_and_replays_exact_proof(self):
        first,last = self.issue('advance_invoice','50.00'),None
        last = self.issue('final_invoice','100.00',[first['id']])
        self.f.income(first,'59.50')
        payment,event = self.f.imported(amount='59.50')
        before = self.f.snapshot(('business_payments','business_accounting_cash_events','business_accounting_source_links'))
        command = self.f.command(payment,last,'59.50')
        assigned = self.f.alloc.assign(self.owner,payment['id'],command)
        self.assertEqual(self.f.alloc.assign(self.owner,payment['id'],command),assigned)
        self.assertEqual(self.f.snapshot(tuple(before)),before)
        self.f.components.confirm(self.owner,event['id'],self.f.component_confirm_body(event))
        self.assertEqual(self.book_all_cash()['totals']['confirmed_income'],'119.00')

    def test_partial_refund_r1_r2_and_reuse_cannot_borrow_other_chain_capacity(self):
        first,middle,last = self.chain()
        self.f.income(first,'35.70'); self.f.income(middle,'47.60')
        _,_,origin = self.f.income(last,'35.70')
        self.f.bound_return(last,'11.90',origin=origin)
        _,event = self.f.cash_event(last,'11.90')
        reused = self.f.capacity.confirm(self.owner,event['id'],self.f.capacity_command(event))
        self.assertEqual((reused['net'],reused['tax']),('10.00','1.90'))
        _,refund = self.f.cash_event(last,'23.80',kind='refund')
        group = origin['lines'][0]['group_id']
        command = self.f.versioned_command(refund,[('c1',origin['id'],group,'11.90'),('c2',reused['id'],group,'11.90')])
        returned = self.f.r2.confirm(self.owner,refund['id'],command)
        self.assertEqual((returned['net'],returned['tax']),('20.00','3.80'))
        self.assertEqual(self.f.r2.confirm(self.owner,refund['id'],command),returned)
        _,event2 = self.f.cash_event(last,'23.80')
        final = self.f.capacity.confirm(self.owner,event2['id'],self.f.capacity_command(event2))
        self.assertEqual((final['net'],final['tax']),('20.00','3.80'))
        self.assertEqual(self.book_all_cash()['totals']['confirmed_income'],'119.00')

    def test_later_predecessor_cancellation_blocks_new_decisions_but_preserves_history(self):
        first,middle,last = self.chain()
        payment,event,origin = self.f.income(last,'11.90')
        before = canonical(self.f.components.history(self.owner,event['id']))
        chain_hash = hashlib.sha256(canonical(archive_chain(self.office,self.row(last))).encode()).hexdigest()
        draft = self.f.docs.cancel(self.owner,first['id'],self.f.legacy_req(revision=first['revision'],reason='Synthetic predecessor cancellation'))
        self.f.docs.finalize(self.owner,draft['id'],render_prepared(self.f.docs.prepare_finalization(self.owner,draft['id'],draft['revision'])),uuid.uuid4().hex)
        self.assertEqual(eligibility(self.office,self.row(last))[0],'cancelled_invoice_chain')
        self.assertEqual(canonical(self.f.components.history(self.owner,event['id'])),before)
        self.assertEqual(hashlib.sha256(canonical(archive_chain(self.office,self.row(last))).encode()).hexdigest(),chain_hash)
        # Existing economic returns remain documentable against their old lot.
        _,returned = self.f.bound_return(last,'11.90',origin=origin)
        self.assertEqual((returned['net'],returned['tax']),('10.00','1.90'))
        _,new_event = self.f.cash_event(last,'11.90')
        self.assertEqual(self.f.components.state(self.owner,new_event['id'])['blocked_reason'],'cancelled_invoice_chain')

    def test_writer_rejects_overlap_foreign_project_and_archive_relation_corruption(self):
        first,middle,last = self.chain()
        self.f.problem(409,self.issue,'final_invoice','130.00',[first['id'],middle['id']])
        self.f.problem(409,self.issue,'final_invoice','130.00',[last['id']])
        independent = self.issue('advance_invoice','20.00',project=self.f.same_project)
        self.f.problem(409,self.issue,'final_invoice','100.00',[independent['id']])
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_document_relations_update_guard')
            self.office.db.execute("UPDATE business_document_relations SET source_sha256=? WHERE target_id=? AND kind='deducts'",('0'*64,last['id']))
        self.f.problem(409,archive_chain,self.office,self.row(last))

    def test_missing_ancestor_archive_is_never_an_empty_tax_basis(self):
        first,middle,last=self.chain()
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_document_archives_delete_guard')
            self.office.db.execute('DELETE FROM business_document_archives WHERE document_id=?',(first['id'],))
        self.f.problem(409,archive_chain,self.office,self.row(last))

    def test_self_consistent_payload_hash_cannot_hide_a_cyclic_ancestor_graph(self):
        first,middle,last=self.chain()
        value=json.loads(self.row(middle)['payload_json']);value['previous_document_ids']=[last['id']]
        encoded=canonical(value);digest=hashlib.sha256(encoded.encode()).hexdigest()
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_documents_update_guard')
            self.office.db.execute('DROP TRIGGER business_document_archives_update_guard')
            self.office.db.execute('UPDATE business_documents SET payload_json=?,payload_sha256=? WHERE id=?',(encoded,digest,middle['id']))
            self.office.db.execute('UPDATE business_document_archives SET payload_json=?,payload_sha256=? WHERE document_id=?',(encoded,digest,middle['id']))
        self.f.problem(409,archive_chain,self.office,self.row(last))


if __name__ == '__main__':
    unittest.main()
