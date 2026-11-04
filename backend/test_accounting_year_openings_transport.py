"""Actual strict local and MFA HTTP for original journal values and EÜR continuation."""
import unittest
import test_accounting_open_items_transport as item
import test_accounting_openings_transport as fixture

class YearValuesTransportCases:
    path='/business/accounting/year-values'
    test_strict_framing=item.OpeningItemTransportCases.test_strict_framing

    def test_original_limit_replay_and_download(self):
        import base64,hashlib,json,uuid
        raw=b'%PDF-1.4\n'+b'S'*(5*1024*1024-15)+b'\n%%EOF'
        command=dict(request_id=uuid.uuid4().hex,entity_key='2026',filename='historical.pdf',media_type='application/pdf',content_base64=base64.b64encode(raw).decode())
        status,_,data=self.raw('POST','/originals',json.dumps(command).encode());self.assertEqual(status,201,data[:200]);original=json.loads(data)
        self.assertEqual(original['sha256'],hashlib.sha256(raw).hexdigest());before=self.office.db.total_changes
        self.assertEqual(json.loads(self.raw('POST','/originals',json.dumps(command).encode())[2]),original)
        status,headers,data=self.raw('GET','/originals/'+original['id']);self.assertEqual(status,200);self.assertEqual(data,raw);self.assertEqual(headers['Cache-Control'],'no-store')
        command.update(request_id=uuid.uuid4().hex,content_base64=base64.b64encode(raw+b'x').decode())
        self.assertEqual(self.raw('POST','/originals',json.dumps(command).encode())[0],413);self.assertEqual(self.office.db.total_changes,before)

    def test_actual_http_original_year_values_euer_and_exact_lost_ack(self):
        import base64,json,uuid
        from business_accounting_open_items import OpeningItems,public_source as item_source
        from business_accounting_profile import AccountingPreparationProfile
        from business_accounting_euer import EuerAccounting
        import test_business_accounting_open_items as fixtures
        actor=dict(id=self.office.db.execute("SELECT id FROM users WHERE role='owner' ORDER BY id LIMIT 1").fetchone()[0])
        profile=AccountingPreparationProfile(self.office);state=profile.state(actor)
        body=dict(expected_revision=state['revision'],state_hash=state['state_hash'],reason='Synthetic continuous old EÜR/Ist method',evidence_reference='Synthetic original method record',profile=dict(legal_form='sole_proprietorship',accounting_method='euer',vat_regime='regular',vat_timing='cash',vat_effective_from='2025-01-01',bookkeeping_start='2026-11-01'))
        preview=profile.preview(actor,body);profile.confirm(actor,dict(body,request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash']))
        helper=fixtures.OpeningItemWorkflow('runTest');helper.office=self.office;helper.owner=actor;helper.api=OpeningItems(self.office)
        record=helper.item('http-year-supplier','payable');record.update(invoice_date='2026-06-10',service_date='2026-06-10',invoice_received_date='2026-06-11',history_through='2026-10-31')
        record['prior_input_vat'].update(entitlement_date='2026-06-11',declared_period='2026-06',deducted_on='2026-07-10')
        record['prior_payments']=[dict(date='2026-08-20',reference='Actual old August payment',gross='59.50',net='50.00',tax='9.50',proof=record['cutover_proof'])]
        accepted,_=helper.save('item','http-year-supplier',record)
        def call(method,suffix='',value=None,root=None):
            previous=self.path
            try:
                if root:self.path=root
                status,_,payload=self.raw(method,suffix,json.dumps(value).encode() if value is not None else None)
                self.assertIn(status,(200,201),payload[:300]);return json.loads(payload)
            finally:self.path=previous
        original=call('POST','/originals',dict(request_id=uuid.uuid4().hex,entity_key='2026',filename='journal.pdf',media_type='application/pdf',content_base64=base64.b64encode(b'%PDF-1.4\nSynthetic separate complete old journal\n%%EOF').decode()))
        state=call('GET');payload=dict(status='active',coverage={'from':'2026-01-01','through':'2026-10-31'},sources=[dict(kind='opening_item',entry_id=accepted['id'],entry_hash=accepted['content_hash'],accounts=dict(net='5400',tax='1406',input_vat='1406'),cash_entry_keys=['OLD-081'],vat_entry_key='OLD-061')],
             controls=[dict(ledger='euer',category='materials',account='5400',amount='-50.00'),dict(ledger='euer',category='paid_input_vat',account='1406',amount='-9.50'),dict(ledger='vat',category='input_vat',account='1406',amount='-19.00')],ledger_proof=dict(original_id=original['id'],sha256=original['sha256']),attestations=dict(continuous_method=True,original_journal_complete=True,no_unsupported_values=True))
        body=dict(expected_revision=state['revision'],state_hash=state['state_hash'],entity_key='2026',profile_ref=state['profile_ref'],operation='year_values',payload=payload,reason='Complete original period and exact totals reviewed')
        preview=call('POST','/preview',body);command=dict(body,request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash'])
        year=call('POST','/confirm',command);before=self.office.db.total_changes
        self.assertEqual(call('POST','/confirm',command),year);self.assertEqual(self.office.db.total_changes,before)
        source=call('GET','/years/2026?revision=1');self.assertEqual(source['cash_movements'],[])
        def classify(operation,payload):
            api=EuerAccounting(self.office);state=api.state(actor)
            body=dict(operation=operation,expected_revision=state['revision'],state_hash=state['state_hash'],reason='Original year/cash source reviewed',evidence_reference='Synthetic actual HTTP review',payload=payload)
            preview=call('POST','/preview',body,root='/business/accounting/euer');return call('POST','/confirm',dict(body,request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash']),root='/business/accounting/euer')
        classify('opening_year_values',dict(year='2026',revision=1,source_hash=source['source_hash']))
        key=uuid.uuid4().hex;paid,_=helper.save('payment',key,dict(status='active',item_key=accepted['entity_key'],item_id=accepted['id'],item_hash=accepted['content_hash'],date='2026-11-01',amount='59.50',account_id=self.account['id'],account_revision=1,evidence_reference='Actual November payment '+key,proof=helper.original(accepted['entity_key'],'actual November transfer '+key)))
        source=item_source(self.office,key);classify('opening_item_cash',dict(payment_id=key,revision=1,source_hash=source['source_hash'],net_account='5400',tax_account='1406'))
        report=call('GET','/report?year=2026',root='/business/accounting/euer')
        self.assertEqual((report['totals']['confirmed_expenses'],report['totals']['confirmed_input_vat'],report['totals']['euer_surplus']),('119.00','19.00','-119.00'))
        self.assertEqual([m['amount'] for m in report['cash_movements']],['59.50'])

class YearValuesLocalTransport(YearValuesTransportCases,unittest.TestCase):
    setUp=fixture.OpeningLocalTransportTests.setUp
    raw=fixture.OpeningLocalTransportTests.raw

class YearValuesMFATransport(YearValuesTransportCases,unittest.TestCase):
    setUp=fixture.OpeningMFATransportTests.setUp
    raw=fixture.OpeningMFATransportTests.raw
    new_company=fixture.OpeningMFATransportTests.new_company
    open_app=fixture.OpeningMFATransportTests.open_app
    call=fixture.OpeningMFATransportTests.call
    login=fixture.OpeningMFATransportTests.login
    account_record=fixture.OpeningMFATransportTests.account_record

if __name__=='__main__':unittest.main()
