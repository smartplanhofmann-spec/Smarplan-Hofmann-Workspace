"""Dated source original/receipt integrity, authorization, races and real restore."""
from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import unittest
import uuid
import zipfile

from backup import backup
from restore import restore
from core import Office, Problem, canonical
from company_export_archive import build, structure, verify
import business_catalog_prices as prices
import test_business_catalog_prices as fixture_module
from test_business_catalog_prices import request, raw, row


class DatedCatalogEvidenceTests(unittest.TestCase):
    def setUp(self):
        f=self.f=fixture_module.CatalogPricesTests()
        self.addCleanup(f.doCleanups)
        f.setUp()
        self.office,self.owner,self.service=f.office,f.owner,f.service

    def actor(self,role='manager'):
        value=dict(id=uuid.uuid4().hex,role=role,email=uuid.uuid4().hex+'@example.test')
        self.office.db.execute('INSERT INTO users(id,email,role,active) VALUES(?,?,?,1)',tuple(value[key] for key in ('id','email','role')))
        return value

    def grant(self,actor,permission,effect='allow'):
        self.office.db.execute("INSERT INTO business_permission_grants(id,user_id,permission,scope,effect,revision,updated_by,updated_at) VALUES(?,?,?,'*',?,1,?,?)",
            (uuid.uuid4().hex,actor['id'],permission,effect,self.owner['id'],'2026-11-04'))

    def test_existing_dated_position_cannot_drop_all_source_identity_into_manual_zero(self):
        import test_business_catalog_price_consumers as consumer
        f=consumer.CatalogPriceConsumerTests('runTest');f.setUp();self.addCleanup(f.doCleanups)
        accepted,_=f.accept(f.stage());document=f.draft(positions=[f.position(accepted)])
        original=document['positions'][0]
        forged={key:value for key,value in original.items() if key not in ('article_id','article_revision','catalog_price_snapshot')}
        forged['unit_price_net']='0'
        f.problem(409,f.api.update,f.owner,document['id'],request(revision=document['revision'],positions=[forged]))
        self.assertEqual(f.api.get(f.owner,document['id'])['positions'],document['positions'])

    def test_readonly_preview_and_original_require_both_permissions_and_no_nonce_is_written(self):
        staged=self.f.stage()
        actor=self.actor()
        self.grant(actor,'settings.manage');self.grant(actor,'finance.read')
        before=self.office.db.total_changes
        self.service.preview(actor,staged['id'],self.f.choices(staged))
        self.service.original(actor,staged['id'])
        self.assertEqual(self.office.db.total_changes,before)
        checked=self.service.preview(actor,staged['id'],self.f.choices(staged))
        body=request(**self.f.choices(staged),preview_sha256=checked['preview_sha256'],confirmation=True)
        self.f.problem(403,self.service.apply,actor,staged['id'],body)
        self.office.db.execute("UPDATE business_permission_grants SET effect='deny' WHERE user_id=? AND permission='finance.read'",(actor['id'],))
        self.f.problem(403,self.service.original,actor,staged['id'])
        self.grant(actor,'finance.write')
        self.f.problem(403,self.service.create_source,actor,request(name='Denied read',reference='SYN-DENIED'))
        self.f.problem(403,self.service.apply,actor,staged['id'],body)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_catalog_price_applications').fetchone()[0],0)

    def test_receipt_binds_original_even_if_original_and_parsed_hashes_are_rewritten_together(self):
        staged=self.f.stage()
        changed=raw(row(amount='77'))
        self.office.db.execute('DROP TRIGGER business_catalog_price_imports_update_guard')
        self.office.db.execute('UPDATE business_catalog_price_imports SET original=?,original_sha256=?,rows_json=?,rows_sha256=? WHERE id=?',
            (changed,prices.sha(changed),canonical(prices.parse_catalog(changed)),prices.sha(prices.parse_catalog(changed)),staged['id']))
        self.f.problem(409,self.service.original,self.owner,staged['id'])
        with self.assertRaises(ValueError): prices.validate_integrity(self.office)

    def test_index_binding_or_price_revision_tampering_cannot_hide_behind_payload_hash(self):
        accepted,_=self.f.accept(self.f.stage())
        self.office.db.execute('DROP TRIGGER business_catalog_price_events_update_guard')
        self.office.db.execute("UPDATE business_catalog_price_events SET price_key='rewritten-index'")
        self.f.problem(409,self.service.candidates,self.owner,dict(article_id=accepted['bindings'][0]['article_id'],price_role='sales_net',effective_on='2026-11-04'))
        with self.assertRaises(ValueError): prices.validate_integrity(self.office)

    def test_same_nonce_race_accepts_once_and_distinct_stale_application_loses(self):
        staged=self.f.stage()
        decisions=self.f.choices(staged)
        checked=self.service.preview(self.owner,staged['id'],decisions)
        body=request(**decisions,preview_sha256=checked['preview_sha256'],confirmation=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.service.apply(self.owner,staged['id'],body),range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_catalog_price_applications').fetchone()[0],1)
        first=self.f.stage(raw(row(code='RACE-A',price_id='race-a')))
        second=self.f.stage(raw(row(code='RACE-B',price_id='race-b')))
        commands=[]
        for imported in (first,second):
            choices=self.f.choices(imported)
            preview=self.service.preview(self.owner,imported['id'],choices)
            commands.append((imported['id'],request(**choices,preview_sha256=preview['preview_sha256'],confirmation=True)))
        def execute(value):
            try:return self.service.apply(self.owner,*value)
            except Problem as error:return error.status
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(execute,commands))
        self.assertEqual(sum(isinstance(value,dict) for value in results),1)
        self.assertEqual(results.count(409),1)
        prices.validate_integrity(self.office)

    def test_real_sqlite_backup_restore_and_portable_archive_keep_original_and_versions(self):
        original=raw(row(),row(price_id='dec',amount='12',start='2026-12-01',end=''))
        staged=self.f.stage(original)
        accepted,command=self.f.accept(staged)
        snapshot=prices.resolve_selection(self.office,self.owner,accepted['bindings'][0]['article_id'],self.f.selection(accepted),'sales_net')
        expected={table:[tuple(value) for value in self.office.db.execute('SELECT * FROM '+table)] for table in prices.TABLES}
        target=Path(self.f.temp.name)/'dated-backup.sqlite'
        destination=Path(self.f.temp.name)/'dated-restored.sqlite'
        self.office.db.commit()
        backup(Path(self.f.temp.name)/'office.db',target)
        restore(target,destination)
        restored=Office(destination)
        self.addCleanup(restored.db.close)
        prices.validate_integrity(restored)
        self.assertEqual(prices.validate_snapshot(restored,snapshot),snapshot)
        for table,values in expected.items():self.assertEqual([tuple(value) for value in restored.db.execute('SELECT * FROM '+table)],values)
        self.assertEqual(prices.CatalogPrices(restored).original(self.owner,staged['id'])[0],original)
        archive,_=build(restored,instance_id='1'*32,export_id='2'*32,created_at='2026-11-04T12:00:00+00:00',created_by=self.owner['id'],reason='Synthetic dated catalog restore',inventory=structure(restored))
        verify(archive,instance_id='1'*32)
        with zipfile.ZipFile(io.BytesIO(archive)) as content:
            imported=json.loads(content.read('data/business_catalog_price_imports.jsonl'))
            self.assertEqual(content.read(imported['original']['$file']),original)
            self.assertEqual(len(content.read('data/business_catalog_price_events.jsonl').splitlines()),2)
            self.assertNotIn('data/business_catalog_price_requests.jsonl',content.namelist())


if __name__=='__main__':unittest.main()
