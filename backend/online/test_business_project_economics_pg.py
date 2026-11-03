"""Actual PostgreSQL/MFA project costs, incremental invoices and cash sources."""
import base64
import json
import unittest
import uuid

import business_schema
from business_project_economics import validate_integrity
from online import test_customer_execution_journey_pg as journey_fixture

fixture = journey_fixture.fixture


def req(**values):
    return dict(request_id=uuid.uuid4().hex, **values)


@unittest.skipUnless(fixture.DSN, 'Disposable loopback SMARTPLAN_TEST_DSN required')
class ProjectEconomicsPostgres(unittest.TestCase):
    setUp = journey_fixture.CustomerExecutionJourneyPostgres.setUp
    reopen = journey_fixture.CustomerExecutionJourneyPostgres.reopen
    call = journey_fixture.CustomerExecutionJourneyPostgres.call
    login = journey_fixture.CustomerExecutionJourneyPostgres.login

    def project(self):
        owner = dict(self.office.db.execute("SELECT * FROM users WHERE email='order-owner@example.test'").fetchone())
        return self.office.add_project(owner, 'Synthetic economics project', 'Synthetic buyer')

    def incoming(self, project):
        receipt = self.call('POST', '/business/finance/receipts', req(project_id=project,
            filename='synthetic-economics.pdf', media_type='application/pdf',
            original_base64=base64.b64encode(b'%PDF-1.4\nSynthetic cost source').decode())).json
        return self.call('POST', '/business/finance/receipts/' + receipt['id'], req(revision=0,
            vendor='Synthetic supplier', invoice_number='SYN-COST-1', issue_date=self.today,
            net='30.00', tax='5.70', gross='35.70', currency='EUR', status='reviewed', note='Original checked')).json

    def classify(self, project, receipt):
        body = dict(project_id=project, receipt_id=receipt['id'], source_revision=receipt['revision'], expected_revision=0,
            allocations=[dict(category='external_service', amount_net='20.00'), dict(category='other', amount_net='10.00')],
            reason='Subcontractor and project consumables verified against original.')
        preview = self.call('POST', '/business/project-economics/preview', body).json
        command = req(**body, preview_hash=preview['preview_hash'])
        result = self.call('POST', '/business/project-economics/confirm', command, status=201).json
        self.assertEqual(self.call('POST', '/business/project-economics/confirm', command, status=201).json, result)
        return result, command

    def issuer(self):
        settings = self.call('GET', '/business/settings/branding').json
        self.call('POST', '/business/settings/branding', req(revision=settings['revision'], company_name='Synthetic issuer',
            address_line='Synthetic street 1', postal_code='10115', city='Berlin', country='DE', vat_id='DE123456789',
            email='issuer@example.test', issuer_mode='own', issuing_enabled=True, cutover_ack=True,
            cutover_date=self.today, einvoice_format='none'))

    def invoice(self, project, amount, *, kind='invoice', previous=None):
        draft = self.call('POST', '/business/documents', req(project_id=project, kind=kind, title='Synthetic '+kind,
            issue_date=self.today, due_date=self.today,
            buyer=dict(name='Synthetic buyer', address_line='Synthetic buyer street', postal_code='10117', city='Berlin', country='DE'),
            positions=[dict(description='Synthetic project work', quantity='1', unit='C62', unit_price_net=amount,
                            tax_rate='19', kind='service')], **({'previous_document_ids': previous} if previous else {}))).json
        return self.call('POST', '/business/documents/' + draft['id'] + '/finalize', req(revision=draft['revision'])).json

    def payment(self, document, amount, *, kind='receipt'):
        return self.call('POST', '/business/finance/payments', req(source_id='synthetic-'+uuid.uuid4().hex, kind=kind,
            amount=amount, currency='EUR', booking_date=self.today, reference='Synthetic recorded bank source',
            allocations=[dict(document_id=document['id'], amount=amount)])).json

    def test_full_cost_revenue_payment_chain_uses_incremental_invoices_and_original_sources(self):
        self.assertTrue(business_schema.require_runtime_security(self.office))
        project = self.project(); receipt = self.incoming(project)
        entry, command = self.classify(project, receipt)
        self.issuer()
        advance = self.invoice(project, '50.00', kind='advance_invoice')
        final = self.invoice(project, '100.00', kind='final_invoice', previous=[advance['id']])
        self.assertEqual(final['totals']['net'], '50.00')
        self.assertEqual(final['contract_totals']['net'], '100.00')
        self.payment(advance, '59.50'); self.payment(final, '59.50')
        result = self.call('GET', '/business/project-economics?project_id=' + project).json
        self.assertEqual(result['revenue']['revenue_net'], '100.00')
        self.assertEqual(result['payments']['net_inflow_gross'], '119.00')
        self.assertEqual(result['payments']['open_gross'], '0.00')
        self.assertEqual(result['result']['document_net_contribution'], '70.00')
        account = self.call('POST', '/business/accounting/accounts', req(confirmation=True, code='BANK', name='Synthetic bank', kind='bank'), status=201).json
        source = next(item for item in self.call('GET', '/business/accounting/sources/receipts').json['items'] if item['receipt_id'] == receipt['id'])
        payout = self.call('POST', '/business/accounting/events/payout', req(confirmation=True, receipt_id=receipt['id'],
            source_hash=source['source_hash'], review_revision=source['review_revision'], review_sha256=source['review_sha256'],
            original_sha256=source['original_sha256'], account_id=account['id'], account_revision=account['revision'],
            expected_cash_revision=source['cash_revision'], amount='20.00', cash_date=self.today,
            evidence_reference='Synthetic bank payout 1', reference='Partial supplier payment'), status=201).json
        result = self.call('GET', '/business/project-economics?project_id=' + project).json
        self.assertEqual(result['payments']['supplier_outflows_gross'], '20.00')
        self.assertEqual(result['payments']['cash_balance_gross'], '99.00')
        self.assertEqual(result['result']['document_net_contribution'], '70.00')
        self.assertEqual(result['sources']['supplier_payments'][0]['event_id'], payout['id'])
        cancelled = self.call('POST', '/business/documents/' + final['id'] + '/cancel', req(revision=final['revision'], reason='Synthetic cancelled remaining work')).json
        self.call('POST', '/business/documents/' + cancelled['id'] + '/finalize', req(revision=cancelled['revision']))
        self.payment(final, '59.50', kind='refund')
        result = self.call('GET', '/business/project-economics?project_id=' + project).json
        self.assertEqual(result['revenue']['revenue_net'], '50.00')
        self.assertEqual(result['payments']['net_inflow_gross'], '59.50')
        self.assertEqual(result['payments']['open_gross'], '0.00')
        self.assertEqual(result['payments']['cash_balance_gross'], '39.50')
        self.assertEqual(result['result']['document_net_contribution'], '20.00')
        preserved = json.dumps(result, sort_keys=True)
        self.reopen()
        self.assertEqual(json.dumps(self.call('GET', '/business/project-economics?project_id=' + project).json, sort_keys=True), preserved)
        self.assertEqual(self.call('POST', '/business/project-economics/confirm', command, status=201).json, entry)
        validate_integrity(self.office)
        # Immutable runtime role, not an application-side convention.
        with self.assertRaises(Exception):
            with self.office.db:
                self.office.db.execute('DELETE FROM business_project_cost_versions WHERE id=?', (entry['id'],))

    def test_receipt_revision_conflict_scope_methods_and_device_tokens_remain_bounded(self):
        project = self.project(); receipt = self.incoming(project)
        entry, command = self.classify(project, receipt)
        changed = dict(command, request_id=uuid.uuid4().hex)
        conflict = self.call('POST', '/business/project-economics/confirm', changed, status=409).json
        self.assertEqual(conflict['request_resolution'], 'not_accepted')
        same_id_changed = self.call('POST', '/business/project-economics/confirm', dict(command, reason='Different body'), status=409).json
        self.assertNotIn('request_resolution', same_id_changed)
        grant = self.call('POST', '/business/offline/access', {}, status=201).json['token']
        self.call('GET', '/business/project-economics?project_id=' + project, token=grant, status=403)
        self.call('POST', '/business/project-economics/confirm', command, token=grant, status=403)
        self.call('GET', '/business/project-economics?project_id=' + project + '&project_id=' + project, status=400)
        self.call('POST', '/business/project-economics/confirm?project_id=' + project, command, status=400)
        self.call('GET', '/business/project-economics?project_id=' + project, {'unexpected': True}, status=400)
        self.assertEqual(self.call('GET', '/business/project-economics/receipts/' + receipt['id'] + '?project_id=' + project).json['items'], [entry])

    def test_project_reader_gets_only_own_mixed_payment_share_and_no_cash_account_details(self):
        from business_foundation import BusinessFoundation
        owner = dict(self.office.db.execute("SELECT * FROM users WHERE email='order-owner@example.test'").fetchone())
        project = self.project()
        private = self.office.add_project(owner, 'Private unrelated project', 'Private unrelated buyer')
        tech_id = self.office.add_user('economics-tech@example.test', 'Synthetic-technician-password', 'technician')
        self.office.assign(owner, project, tech_id)
        BusinessFoundation(self.office).save_grant(owner, req(user_id=tech_id, permission='finance.read', scope=project, effect='allow', revision=0))
        self.issuer(); public_invoice = self.invoice(project, '100.00'); private_invoice = self.invoice(private, '100.00')
        self.call('POST', '/business/finance/payments', req(source_id='synthetic-mixed-payment', kind='receipt',
            amount='238.00', currency='EUR', booking_date=self.today, reference='PRIVATE MIXED BANK REFERENCE',
            allocations=[dict(document_id=item['id'], amount='119.00') for item in (public_invoice, private_invoice)]))
        token = self.login('economics-tech@example.test', 'Synthetic-technician-password')
        result = self.call('GET', '/business/project-economics?project_id=' + project, token=token).json
        self.assertEqual(result['payments']['receipts_gross'], '119.00')
        self.assertFalse(result['payments']['complete'])
        self.assertIsNone(result['payments']['supplier_outflows_gross'])
        self.assertIsNone(result['payments']['cash_balance_gross'])
        self.assertEqual(len(result['sources']['payment_allocations']), 1)
        self.assertNotIn('238.00', json.dumps(result))
        self.assertNotIn('PRIVATE MIXED BANK REFERENCE', json.dumps(result))
        self.assertNotIn(private_invoice['id'], json.dumps(result))
        self.call('GET', '/business/project-economics?project_id=' + private, token=token, status=404)


if __name__ == '__main__':
    unittest.main()
