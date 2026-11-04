"""Real local HTTP routes, strict framing, bounded original and readonly checks."""
import base64
import unittest

import test_business_catalog_imports_transport as transport
from test_business_catalog_prices import raw, row


class DatedCatalogHTTP(transport.CatalogImportLocalHTTP):
    # Reuse server/socket helpers; the v1 test methods are not repeated here.
    test_two_mib_original_uses_bounded_envelope_downloads_exactly_and_replays_once = None
    test_decoded_size_envelope_other_route_and_strict_framing_reject_without_runs = None

    def setUp(self):
        super().setUp()
        self.source=self.call('POST','/api/business/catalog-prices/sources',transport.request(name='Synthetic dated HTTP',reference='SYN-HTTP-V2'))
        self.path='/api/business/catalog-prices/sources/'+self.source['id']+'/imports'

    def stage(self,original=None):
        original=original or raw(row())
        body=transport.request(catalog_revision='SYN-1',filename='dated-v2.csv',content_base64=base64.b64encode(original).decode())
        result=self.call('POST',self.path,body)
        self.assertEqual(self.call('POST',self.path,body),result)
        return result

    def test_actual_two_mib_original_and_import_replay_are_byte_exact(self):
        original=raw(row())
        original+=b'\n'*(2097152-len(original))
        imported=self.stage(original)
        self.assertEqual(imported['original']['size'],2097152)
        self.assertEqual(self.call('GET','/api/business/catalog-prices/imports/'+imported['id']+'/original'),original)
        self.assertEqual(self.call('GET',self.path)['total'],1)
        self.call('POST',self.path,transport.request(catalog_revision='SYN-2',filename='too-large.csv',content_base64=base64.b64encode(b'x'*2097153).decode()),status=413)
        self.call('POST',self.path,{},status=413,headers={'Content-Length':'2850001'})

    def test_unicode_binding_envelope_larger_than_default_json_limit_remains_bounded(self):
        import json
        rows=[row(price_id='P'+str(index),code='😀'*95+str(index)) for index in range(1000)]
        imported=self.stage(raw(*rows))
        decision=dict(expected_source_version=0,replacements={},bindings={item[1]:dict(action='create',article_id=None,article_revision=None,expected_binding_revision=0,confirm_name_difference=False) for item in rows})
        self.assertGreater(len(json.dumps(decision).encode()),1000000)
        before=self.office.db.execute('SELECT COUNT(*) FROM business_articles').fetchone()[0]
        checked=self.call('POST','/api/business/catalog-prices/imports/'+imported['id']+'/preview',decision)
        self.assertEqual(len(checked['rows']),1000)
        self.assertTrue(checked['ready'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_articles').fetchone()[0],before)
        self.call('POST','/api/business/catalog-prices/imports/'+imported['id']+'/preview',{},status=413,headers={'Content-Length':'7100001'})

    def test_strict_channels_and_readonly_preview_do_not_write(self):
        imported=self.stage()
        target='/api/business/catalog-prices/imports/'+imported['id']
        decision=dict(expected_source_version=0,replacements={},bindings={'SYN-PRICE':dict(action='create',article_id=None,article_revision=None,expected_binding_revision=0,confirm_name_difference=False)})
        count=self.office.db.execute('SELECT COUNT(*) FROM audit').fetchone()[0]
        checked=self.call('POST',target+'/preview',decision)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM audit').fetchone()[0],count)
        body=transport.request(**decision,preview_sha256=checked['preview_sha256'],confirmation=True)
        accepted=self.call('POST',target+'/apply',body)
        self.assertEqual(self.call('POST',target+'/apply',body),accepted)
        self.call('POST',target+'/preview?ignored=1',decision,status=400)
        self.call('GET',self.path,{},status=400)
        self.call('GET',self.path+'?limit=1&limit=2',status=400)
        self.call('GET',self.path+'?unknown=1',status=400)
        self.assertEqual(self.call('GET',target)['application'],accepted)
        self.assertEqual(self.call('GET','/api/business/catalog-prices/prices/'+accepted['prices'][0]['price_id']+'/history')['items'][0]['revision'],1)


if __name__=='__main__':
    unittest.main()
