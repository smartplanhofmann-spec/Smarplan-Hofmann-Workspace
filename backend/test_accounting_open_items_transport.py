"""Genuine local HTTP and MFA transport for original-backed open items."""
import unittest
import test_accounting_asset_openings_transport as asset
import test_accounting_openings_transport as fixture

class OpeningItemTransportCases:
    path='/business/accounting/open-items'
    test_strict_framing=asset.AssetTransportCases.test_exact_methods_and_strict_framing_do_not_create_originals

    def test_original_limit_replay_and_download(self):
        # Reuse the real transport boundary case with the additive DTO's key.
        import base64,hashlib,json,uuid
        raw=b'%PDF-1.4\n'+b'S'*(5*1024*1024-15)+b'\n%%EOF'
        command=dict(request_id=uuid.uuid4().hex,entity_key='old-1',filename='old.pdf',media_type='application/pdf',content_base64=base64.b64encode(raw).decode())
        status,_,data=self.raw('POST','/originals',json.dumps(command).encode());self.assertEqual(status,201,data[:200]);original=json.loads(data)
        self.assertEqual(original['sha256'],hashlib.sha256(raw).hexdigest());before=self.office.db.total_changes
        self.assertEqual(json.loads(self.raw('POST','/originals',json.dumps(command).encode())[2]),original)
        status,headers,data=self.raw('GET','/originals/'+original['id']);self.assertEqual(status,200);self.assertEqual(data,raw);self.assertEqual(headers['Cache-Control'],'no-store')
        command.update(request_id=uuid.uuid4().hex,content_base64=base64.b64encode(raw+b'x').decode())
        self.assertEqual(self.raw('POST','/originals',json.dumps(command).encode())[0],413);self.assertEqual(self.office.db.total_changes,before)

    def test_actual_http_item_payment_euer_and_exact_lost_ack_replay(self):
        import json,uuid
        from business_accounting_open_items import OpeningItems
        from business_accounting_profile import AccountingPreparationProfile
        from business_accounting_euer import EuerAccounting
        import test_business_accounting_open_items as fixtures
        actor=dict(id=self.office.db.execute("SELECT id FROM users WHERE role='owner' ORDER BY id LIMIT 1").fetchone()[0])
        profile=AccountingPreparationProfile(self.office);state=profile.state(actor)
        body=dict(expected_revision=state['revision'],state_hash=state['state_hash'],reason='Synthetic proven old ongoing EÜR/Ist activity',evidence_reference='Synthetic historical tax originals',profile=dict(legal_form='sole_proprietorship',accounting_method='euer',vat_regime='regular',vat_timing='cash',vat_effective_from='2025-01-01',bookkeeping_start='2026-01-01'))
        preview=profile.preview(actor,body);profile.confirm(actor,dict(body,request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash']))
        helper=fixtures.OpeningItemWorkflow('runTest');helper.office=self.office;helper.owner=actor;helper.api=OpeningItems(self.office)
        def call(method,suffix='',value=None,root=None):
            previous=self.path
            try:
                if root:self.path=root
                status,_,payload=self.raw(method,suffix,json.dumps(value).encode() if value is not None else None)
                self.assertIn(status,(200,201),payload[:300]);return json.loads(payload)
            finally:self.path=previous
        item=helper.item('http-supplier','payable');body=helper.body('item','http-supplier',item)
        preview=call('POST','/preview',body);command=dict(body,request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash'])
        accepted=call('POST','/confirm',command);before=self.office.db.total_changes
        self.assertEqual(call('POST','/confirm',command),accepted);self.assertEqual(self.office.db.total_changes,before)
        key=uuid.uuid4().hex
        payload=dict(status='active',item_key=accepted['entity_key'],item_id=accepted['id'],item_hash=accepted['content_hash'],date='2026-02-15',amount='119.00',account_id=self.account['id'],account_revision=1,evidence_reference='Synthetic actual HTTP transfer '+key,proof=helper.original('http-supplier','actual HTTP payment '+key))
        body=helper.body('payment',key,payload);preview=call('POST','/preview',body);command=dict(body,request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash'])
        paid=call('POST','/confirm',command);self.assertEqual(call('POST','/confirm',command),paid)
        source=call('GET','/payments/'+key+'?revision=1');self.assertEqual(source['gross'],'119.00')
        euer=EuerAccounting(self.office);state=euer.state(actor)
        body=dict(operation='opening_item_cash',expected_revision=state['revision'],state_hash=state['state_hash'],reason='Actual original supplier payment',evidence_reference='Synthetic HTTP review',payload=dict(payment_id=key,revision=1,source_hash=source['source_hash'],net_account='5400',tax_account='1406'))
        preview=call('POST','/preview',body,root='/business/accounting/euer');call('POST','/confirm',dict(body,request_id=uuid.uuid4().hex,confirmation=True,preview_hash=preview['preview_hash']),root='/business/accounting/euer')
        report=call('GET','/report?year=2026',root='/business/accounting/euer')
        self.assertEqual((report['totals']['confirmed_expenses'],report['totals']['confirmed_input_vat']),('119.00','0.00'))

class OpeningItemLocalTransport(OpeningItemTransportCases,unittest.TestCase):
    setUp=fixture.OpeningLocalTransportTests.setUp
    raw=fixture.OpeningLocalTransportTests.raw

class OpeningItemMFATransport(OpeningItemTransportCases,unittest.TestCase):
    setUp=fixture.OpeningMFATransportTests.setUp
    raw=fixture.OpeningMFATransportTests.raw
    new_company=fixture.OpeningMFATransportTests.new_company
    open_app=fixture.OpeningMFATransportTests.open_app
    call=fixture.OpeningMFATransportTests.call
    login=fixture.OpeningMFATransportTests.login
    account_record=fixture.OpeningMFATransportTests.account_record

if __name__=='__main__':unittest.main()
