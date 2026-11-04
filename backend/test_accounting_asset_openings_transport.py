"""Historical originals through actual local HTTP and MFA routes, synthetic only."""
import base64
import hashlib
import json
import unittest
import uuid

import test_accounting_openings_transport as fixtures


class AssetTransportCases:
    path='/business/accounting/historical-assets'

    def test_exact_methods_and_strict_framing_do_not_create_originals(self):
        before=self.office.db.total_changes
        self.assertEqual(self.raw('GET')[0],200)
        self.assertEqual(self.raw('GET',body=b'{}')[0],400)
        self.assertEqual(self.raw('GET','/history?asset_key=x&asset_key=y')[0],400)
        for suffix in ('/originals','/preview','/confirm'):
            self.assertEqual(self.raw('GET',suffix)[0],405)
            self.assertEqual(self.raw('POST',suffix+'?extra=1',b'{}')[0],400)
            self.assertEqual(self.raw('POST',suffix,b'{"request_id":"x","request_id":"y"}')[0],400)
            self.assertEqual(self.raw('POST',suffix,b'[]')[0],400)
        self.assertEqual(self.office.db.total_changes,before)

    def test_server_identity_uses_exact_unicode_casefold_without_mutating_database(self):
        before=self.office.db.total_changes
        status,_,payload=self.raw('POST','/identity',json.dumps(dict(inventory_number=' ＭAẞE-01 ')).encode())
        self.assertEqual(status,200)
        self.assertEqual(json.loads(payload),dict(schema_version=1,inventory_number=' ＭAẞE-01 ',asset_key='masse-01'))
        self.assertEqual(self.raw('POST','/identity',b'{"inventory_number":"x","extra":true}')[0],400)
        self.assertEqual(self.office.db.total_changes,before)

    def test_five_mib_original_exact_replay_download_and_oversize(self):
        raw=b'%PDF-1.4\n'+b'S'*(5*1024*1024-15)+b'\n%%EOF'
        body=dict(request_id=uuid.uuid4().hex,asset_key='historical-machine',filename='synthetic-asset.pdf',
                  media_type='application/pdf',content_base64=base64.b64encode(raw).decode())
        status,_,payload=self.raw('POST','/originals',json.dumps(body).encode())
        self.assertEqual(status,201,payload[:200]);original=json.loads(payload)
        self.assertEqual(original['sha256'],hashlib.sha256(raw).hexdigest())
        before=self.office.db.total_changes
        self.assertEqual(json.loads(self.raw('POST','/originals',json.dumps(body).encode())[2]),original)
        status,headers,download=self.raw('GET','/originals/'+original['id'])
        self.assertEqual(status,200);self.assertEqual(download,raw)
        self.assertEqual(headers['Cache-Control'],'no-store');self.assertEqual(headers['Content-Type'],'application/pdf')
        self.assertTrue(headers['Content-Disposition'].startswith('attachment;'))
        oversized=body|dict(request_id=uuid.uuid4().hex,content_base64=base64.b64encode(raw+b'x').decode())
        self.assertEqual(self.raw('POST','/originals',json.dumps(oversized).encode())[0],413)
        self.assertEqual(self.office.db.total_changes,before)


class HistoricalAssetLocalTransport(AssetTransportCases,unittest.TestCase):
    setUp=fixtures.OpeningLocalTransportTests.setUp
    raw=fixtures.OpeningLocalTransportTests.raw


class HistoricalAssetMFATransport(AssetTransportCases,unittest.TestCase):
    setUp=fixtures.OpeningMFATransportTests.setUp
    raw=fixtures.OpeningMFATransportTests.raw
    new_company=fixtures.OpeningMFATransportTests.new_company
    open_app=fixtures.OpeningMFATransportTests.open_app
    call=fixtures.OpeningMFATransportTests.call
    login=fixtures.OpeningMFATransportTests.login
    account_record=fixtures.OpeningMFATransportTests.account_record
    test_json_media_type=fixtures.OpeningMFATransportTests.test_mfa_api_requires_json_media_type_before_original_acceptance


if __name__=='__main__':unittest.main()
