"""Synthetic persisted documentation workflows; no providers or real customer files."""
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import uuid
import weakref

from core import Office, Problem
from business_operations import BusinessOperations, CHUNK_SIZE, schema_statements, validate_integrity
import business_operations as domain

from PIL import Image
_png = io.BytesIO()
Image.new('RGB', (8, 8), '#aabbcc').save(_png, format='PNG')
PNG = _png.getvalue()


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.office = Office(Path(self.temp.name) / 'office.db')
        self.addCleanup(self.office.db.close)
        from business_foundation import schema_statements as foundation_schema
        for statement in foundation_schema('BLOB') + schema_statements('BLOB'):
            self.office.db.execute(statement)
        self.office.db.commit()
        self.owner = self.actor('owner')
        self.tech = self.actor('technician')
        self.outsider = self.actor('technician')
        self.project = self.office.add_project(self.owner, 'Synthetic site', 'Synthetic customer')
        self.other = self.office.add_project(self.owner, 'Other site', 'Other customer')
        self.office.assign(self.owner, self.project, self.tech['id'])
        self.api = BusinessOperations(self.office, clock=lambda: datetime(2026, 10, 25, 10, tzinfo=timezone.utc))

    def actor(self, role):
        email = uuid.uuid4().hex + '@example.test'
        return dict(id=self.office.add_user(email, 'Synthetic-password-123', role), role=role, email=email)

    def request(self, **data):
        return dict(request_id=uuid.uuid4().hex, **data)

    def error(self, status, function, *args):
        with self.assertRaises(Problem) as caught:
            function(*args)
        self.assertEqual(caught.exception.status, status, caught.exception.message)

    def upload(self):
        body = self.request(filename='synthetic.png', media_type='image/png', size=len(PNG), sha256=hashlib.sha256(PNG).hexdigest())
        media = self.api.new_media(self.tech, self.project, body)
        self.api.put_media_chunk(self.tech, self.project, media['id'], 0, PNG)
        self.api.complete_media(self.tech, self.project, media['id'], self.request())
        return self.api.get_media(self.tech, self.project, media['id'])

    def test_source_hash_original_and_annotations_are_independent(self):
        media = self.upload()
        changed = self.api.annotate_media(self.tech, self.project, media['id'], self.request(
            revision=media['revision'], caption='Synthetic measurement mark', annotations=[
                {'kind': 'line', 'points': [[0.1, 0.2], [0.8, 0.2]], 'color': '#ff0000'},
                {'kind': 'text', 'point': [0.1, 0.3], 'text': 'Check locally'}]))
        self.assertEqual(changed['revision'], media['revision'] + 1)
        self.assertEqual(self.api.media_source(self.tech, self.project, media['id']), PNG)
        self.assertEqual(changed['sha256'], hashlib.sha256(PNG).hexdigest())
        self.assertEqual(self.api.list_media(self.tech, self.project)[0], changed)
        self.assertTrue(validate_integrity(self.office))

    def test_gallery_and_detail_metadata_never_read_original_blobs_or_release_private_files(self):
        ready = self.upload()
        private = self.upload()
        self.api.annotate_media(self.owner, self.project, private['id'], self.request(
            revision=private['revision'], classification='financial'))
        partial = self.api.new_media(self.tech, self.project, self.request(filename='unfinished.png',
            media_type='image/png', size=len(PNG), sha256=hashlib.sha256(PNG).hexdigest()))
        self.api.put_media_chunk(self.tech, self.project, partial['id'], 0, PNG)
        expected = self.api.list_media(self.tech, self.project)
        denied = []

        def deny_original_reads(action, table, column, database, trigger):
            if action == sqlite3.SQLITE_READ and table == 'business_media' and column == 'original':
                denied.append((table, column))
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        self.office.db.set_authorizer(deny_original_reads)
        try:
            self.assertEqual(self.api.list_media(self.tech, self.project), expected)
            self.assertEqual(self.api.get_media(self.tech, self.project, ready['id']), ready)
            self.assertEqual(self.api.get_media(self.tech, self.project, partial['id'])['uploaded_chunks'], [0])
            self.error(403, self.api.get_media, self.tech, self.project, private['id'])
            self.assertEqual(denied, [], 'Metadata or authorization attempted to read an original BLOB')
            # The explicit binary source operation must still read its original;
            # the metadata optimization must not synthesize or truncate bytes.
            with self.assertRaises(sqlite3.DatabaseError):
                self.api.media_source(self.tech, self.project, ready['id'])
            self.assertEqual(denied, [('business_media', 'original')])
        finally:
            self.office.db.set_authorizer(None)
        content = self.api.media_source(self.tech, self.project, ready['id'])
        self.assertEqual(content, PNG)
        self.assertEqual(hashlib.sha256(content).hexdigest(), ready['sha256'])
        self.error(403, self.api.media_source, self.tech, self.project, private['id'])

    def test_integrity_materializes_one_original_at_a_time_and_checks_the_last_file(self):
        photos = [self.upload() for _ in range(3)]
        original_factory = self.office.db.row_factory
        retained = weakref.WeakValueDictionary()
        peak = [0]

        class ObservedOriginalRow(dict):
            pass

        def observe_originals(cursor, values):
            row = original_factory(cursor, values)
            if 'original' in row.keys() and row['original'] is not None:
                row = ObservedOriginalRow((key, row[key]) for key in row.keys())
                retained[id(row)] = row
                peak[0] = max(peak[0], len(retained))
            return row

        self.office.db.row_factory = observe_originals
        try:
            self.assertTrue(validate_integrity(self.office))
            self.assertEqual(peak[0], 1, 'Integrity checking retained multiple original BLOB rows')
        finally:
            self.office.db.row_factory = original_factory
        last = max(photos, key=lambda item: item['id'])
        with self.office.db:
            self.office.db.execute('UPDATE business_media SET original=? WHERE id=?',
                                   (PNG[:-1] + bytes([PNG[-1] ^ 1]), last['id']))
        with self.assertRaises(ValueError):
            validate_integrity(self.office)
        # SQLite permits NULL in a TEXT primary key. Corruption must fail
        # closed instead of making a keyset scan repeat its first row forever.
        with self.office.db:
            self.office.db.execute('UPDATE business_media SET original=?,id=NULL WHERE id=?', (PNG, last['id']))
        with self.assertRaises(ValueError):
            validate_integrity(self.office)

    def test_incomplete_wrong_hash_header_and_idempotent_chunks(self):
        media = self.api.new_media(self.tech, self.project, self.request(filename='broken.png', media_type='image/png',
                                  size=len(PNG), sha256='0' * 64))
        self.error(409, self.api.media_source, self.tech, self.project, media['id'])
        self.api.put_media_chunk(self.tech, self.project, media['id'], 0, PNG)
        self.api.put_media_chunk(self.tech, self.project, media['id'], 0, PNG)
        self.error(409, self.api.put_media_chunk, self.tech, self.project, media['id'], 0, b'x' * len(PNG))
        self.error(409, self.api.complete_media, self.tech, self.project, media['id'], self.request())
        fake = b'not an image'
        row = self.api.new_media(self.tech, self.project, self.request(filename='fake.jpg', media_type='image/jpeg',
                                size=len(fake), sha256=hashlib.sha256(fake).hexdigest()))
        self.api.put_media_chunk(self.tech, self.project, row['id'], 0, fake)
        self.error(400, self.api.complete_media, self.tech, self.project, row['id'], self.request())

    def test_replay_scope_and_revoked_actor_rechecked(self):
        body = self.request(filename='synthetic.png', media_type='image/png', size=len(PNG), sha256=hashlib.sha256(PNG).hexdigest())
        original = self.api.new_media(self.tech, self.project, body)
        self.assertEqual(self.api.new_media(self.tech, self.project, body), original)
        self.error(409, self.api.new_media, self.tech, self.project, dict(body, filename='other.png'))
        self.error(404, self.api.get_media, self.outsider, self.project, original['id'])
        self.error(404, self.api.get_media, self.owner, self.other, original['id'])
        with self.office.db:
            self.office.db.execute('UPDATE users SET active=0 WHERE id=?', (self.tech['id'],))
        self.error(401, self.api.new_media, self.tech, self.project, body)

    def measurement(self):
        return self.api.save_entry(self.tech, self.project, 'measurement', self.request(title='Synthetic room', lines=[
            {'description': 'Floor', 'unit': 'm2', 'formula': 'length * width',
             'variables': {'length': {'value': '3.10', 'unit': 'm'}, 'width': {'value': '2.20', 'unit': 'm'}}}]))

    def test_measurement_decimal_formula_and_unit_validation(self):
        row = self.measurement()
        self.assertEqual(row['lines'][0]['quantity'], '6.8200')
        self.assertEqual(row['lines'][0]['formula'], 'length * width')
        for formula, unit in [('__import__("os")', 'm2'), ('length / 0', 'm'), ('length + width', 'm2')]:
            self.error(400, self.api.save_entry, self.tech, self.project, 'measurement', self.request(title='Invalid', lines=[
                {'description': 'Invalid', 'unit': unit, 'formula': formula,
                 'variables': {'length': {'value': '1', 'unit': 'm'}, 'width': {'value': '2', 'unit': 'm'}}}]))

    def test_signature_freezes_exact_content_pdf_and_survives_reopen(self):
        row = self.measurement()
        sign = self.request(revision=1, expected_hash=row['content_hash'], signer='Synthetic Signer', strokes=[[[0.1,0.2],[0.8,0.6]]])
        self.error(409, self.api.sign_entry, self.tech, self.project, row['id'], dict(sign, expected_hash='0'*64))
        signed = self.api.sign_entry(self.tech, self.project, row['id'], sign)
        self.assertEqual(signed['status'], 'signed')
        self.assertEqual(self.api.sign_entry(self.tech, self.project, row['id'], sign), signed)
        pdf = self.api.entry_pdf(self.tech, self.project, row['id'])
        self.assertTrue(pdf.startswith(b'%PDF-'))
        self.assertIn(b'Synthetic Signer', pdf)
        self.assertIn(b'2026-10-25T10:00:00+00:00', pdf)
        self.assertEqual(hashlib.sha256(pdf).hexdigest(), signed['pdf_sha256'])
        self.error(409, self.api.save_entry, self.tech, self.project, 'measurement', self.request(revision=2,title='Overwrite', lines=[]), row['id'])
        second = Office(self.office.path if hasattr(self.office, 'path') else Path(self.temp.name) / 'office.db')
        try:
            self.assertEqual(BusinessOperations(second).entry_pdf(self.owner, self.project, row['id']), pdf)
        finally:
            second.db.close()
        self.assertTrue(validate_integrity(self.office))

    def test_diary_defect_revisions_and_media_binding(self):
        media = self.upload()
        diary = self.api.save_entry(self.tech, self.project, 'diary', self.request(title='Synthetic day', entry_date='2026-10-25',
            work='Installed synthetic cable', weather='Dry', crew_count=2, media_ids=[media['id']]))
        defect = self.api.save_entry(self.tech, self.project, 'defect', self.request(title='Synthetic defect', details='Check cover',
            location='Room 2', due_date='2026-10-30', assignee_id=self.tech['id'], media_ids=[media['id']]))
        done = self.api.save_entry(self.tech, self.project, 'defect', self.request(revision=1,status='resolved',resolution='Cover replaced'),defect['id'])
        self.assertEqual(done['status'], 'resolved')
        self.error(409,self.api.save_entry,self.tech,self.project,'defect',self.request(revision=1,status='open'),defect['id'])
        self.error(400,self.api.save_entry,self.owner,self.other,'diary',self.request(title='Cross-project',media_ids=[media['id']]))
        self.assertEqual(self.api.list_entries(self.owner,self.project,'diary'),[diary])
        self.assertTrue(validate_integrity(self.office))

    def test_checklist_required_answers_freeze_template_and_service_provenance(self):
        template = self.api.save_checklist(self.tech,self.project,self.request(title='Safety checks',items=[
            {'key':'power','label':'Power isolated','required':True,'type':'boolean'},
            {'key':'note','label':'Note','required':False,'type':'text'}]))
        run = self.api.start_checklist(self.tech,self.project,template['id'],self.request())
        self.error(409,self.api.report_from_checklist,self.tech,self.project,run['id'],self.request())
        self.api.save_checklist(self.tech,self.project,self.request(revision=1,title='Changed',items=[
            {'key':'new','label':'New','required':True,'type':'boolean'}]),template['id'])
        answered = self.api.answer_checklist(self.tech,self.project,run['id'],self.request(revision=1,answers={'power':True,'note':'Synthetic safe'}))
        report = self.api.report_from_checklist(self.tech,self.project,run['id'],self.request())
        self.assertEqual(report['kind'],'service')
        self.assertEqual(report['checklist']['template_revision'],1)
        self.assertEqual(report['checklist']['answers'],answered['answers'])
        self.assertEqual(report['checklist']['items'][0]['key'],'power')
        self.assertTrue(validate_integrity(self.office))

    def test_media_classification_applies_to_list_source_annotations_replay_and_receipt_route(self):
        body=self.request(filename='site.png',media_type='image/png',size=len(PNG),sha256=hashlib.sha256(PNG).hexdigest())
        media=self.api.new_media(self.tech,self.project,body)
        self.api.put_media_chunk(self.tech,self.project,media['id'],0,PNG)
        self.api.complete_media(self.tech,self.project,media['id'],self.request())
        current=self.api.get_media(self.owner,self.project,media['id'])
        self.api.annotate_media(self.owner,self.project,media['id'],self.request(revision=current['revision'],classification='financial'))
        self.assertEqual(self.api.list_media(self.tech,self.project),[])
        for function,args in ((self.api.get_media,(self.tech,self.project,media['id'])),
                              (self.api.media_source,(self.tech,self.project,media['id'])),
                              (self.api.new_media,(self.tech,self.project,body)),
                              (self.api.annotate_media,(self.tech,self.project,media['id'],self.request(revision=3,caption='leak')))):
            self.error(403,function,*args)
        self.error(403,domain.dispatch,self.office,self.tech,'/receipt-media','POST',dict(body,project_id=self.project,classification='operational'))
        self.error(400,domain.dispatch,self.office,self.owner,'/receipt-media','POST',dict(body,request_id=uuid.uuid4().hex,project_id=self.project,classification='operational'))
        self.error(403,self.api.new_media,self.tech,self.project,self.request(filename='unknown.pdf',media_type='application/pdf',size=12,sha256='0'*64))
        self.assertTrue(validate_integrity(self.office))

    def test_chunk_resume_and_original_retention_after_connection_reopen(self):
        import random
        raw=random.Random(17).randbytes(400*400*3)
        stream=io.BytesIO(); Image.frombytes('RGB',(400,400),raw).save(stream,format='PNG')
        content=stream.getvalue(); self.assertGreater(len(content),CHUNK_SIZE)
        media=self.api.new_media(self.tech,self.project,self.request(filename='synthetic-noise.png',media_type='image/png',size=len(content),sha256=hashlib.sha256(content).hexdigest()))
        self.api.put_media_chunk(self.tech,self.project,media['id'],1,content[CHUNK_SIZE:])
        self.error(409,self.api.complete_media,self.tech,self.project,media['id'],self.request())
        second=Office(Path(self.temp.name)/'office.db')
        try:
            resumed=BusinessOperations(second)
            self.assertEqual(resumed.get_media(self.tech,self.project,media['id'])['uploaded_chunks'],[1])
            resumed.put_media_chunk(self.tech,self.project,media['id'],0,content[:CHUNK_SIZE])
            resumed.complete_media(self.tech,self.project,media['id'],self.request())
            self.assertEqual(resumed.media_source(self.tech,self.project,media['id']),content)
            self.assertTrue(validate_integrity(second))
        finally: second.db.close()

    def test_signature_rechecks_scope_after_render_and_never_publishes_removed_project(self):
        row=self.measurement(); original=domain._render_pdf
        def rendering(value):
            pdf=original(value)
            self.office.assign(self.owner,self.project,self.tech['id'],remove=True)
            return pdf
        with patch.object(domain,'_render_pdf',side_effect=rendering):
            self.error(404,self.api.sign_entry,self.tech,self.project,row['id'],self.request(revision=1,expected_hash=row['content_hash'],signer='Synthetic signer',strokes=[[[0,0],[1,1]]]))
        current=self.api.get_entry(self.owner,self.project,row['id'])
        self.assertEqual(current['status'],'draft')
        self.assertIsNone(self.office.db.execute('SELECT pdf FROM business_operation_entries WHERE id=?',(row['id'],)).fetchone()[0])

    def test_outer_transaction_rollback_removes_record_receipt_and_audit_together(self):
        request=self.request(title='Not committed',work='Synthetic')
        with self.assertRaises(RuntimeError):
            with self.office.db:
                self.office.db.execute("UPDATE projects SET name=name WHERE id=?",(self.project,))
                self.api.save_entry(self.tech,self.project,'diary',request)
                raise RuntimeError('synthetic transaction abort')
        self.assertEqual(self.api.list_entries(self.owner,self.project,'diary'),[])
        self.assertIsNone(self.office.db.execute('SELECT 1 FROM business_operations_requests WHERE request_id=?',(request['request_id'],)).fetchone())

    def test_integrity_rejects_signed_content_mutation_even_with_rewritten_latest_history(self):
        row=self.measurement()
        signed=self.api.sign_entry(self.tech,self.project,row['id'],self.request(revision=1,expected_hash=row['content_hash'],signer='Synthetic signer',strokes=[[[0,0],[1,1]]]))
        with self.office.db:
            payload=json.loads(self.office.db.execute('SELECT payload_json FROM business_operation_entries WHERE id=?',(row['id'],)).fetchone()[0]); payload['title']='Mutated signed title'
            self.office.db.execute('UPDATE business_operation_entries SET payload_json=? WHERE id=?',(json.dumps(payload),row['id']))
            signed['title']=payload['title']
            self.office.db.execute("UPDATE business_operation_versions SET payload_json=? WHERE kind='entry' AND object_id=? AND revision=2",(json.dumps(signed),row['id']))
        with self.assertRaises(ValueError): validate_integrity(self.office)

    def test_scoped_photo_and_finance_receipt_helpers_enforce_semantic_floor_even_for_owner(self):
        photo=self.upload()
        self.assertTrue(domain.own_operational_photo(self.office,self.tech,photo['id']))
        self.assertFalse(domain.own_operational_photo(self.office,self.owner,photo['id']))
        self.error(400,domain.verified_receipt_media,self.office,self.owner,photo['id'],self.project)
        receipt=self.api.new_media(self.owner,self.project,self.request(filename='receipt.png',media_type='image/png',size=len(PNG),sha256=hashlib.sha256(PNG).hexdigest(),purpose='receipt'))
        self.assertFalse(domain.own_operational_photo(self.office,self.owner,receipt['id']))
        self.error(409,domain.verified_receipt_media,self.office,self.owner,receipt['id'],self.project)
        self.api.put_media_chunk(self.owner,self.project,receipt['id'],0,PNG)
        self.api.complete_media(self.owner,self.project,receipt['id'],self.request())
        confirmed=domain.verified_receipt_media(self.office,self.owner,receipt['id'],self.project)
        self.assertEqual((confirmed['bytes'],confirmed['sha256']),(PNG,hashlib.sha256(PNG).hexdigest()))
        self.error(404,domain.verified_receipt_media,self.office,self.owner,receipt['id'],self.other)
        self.error(403,domain.verified_receipt_media,self.office,self.tech,receipt['id'],self.project)

    def test_client_cannot_forge_a_service_checklist_provenance_snapshot(self):
        self.error(400,self.api.save_entry,self.tech,self.project,'service',self.request(title='Fake proof',description='Synthetic',checklist={
            'run_id':'f'*32,'template_id':'e'*32,'template_revision':1,'items':[],'answers':{}}))

    def test_restricted_pdf_does_not_become_readable_from_financial_permission_alone(self):
        accountant=self.actor('accountant');self.office.assign(self.owner,self.project,accountant['id'])
        original=b'%PDF-1.4\n%%EOF\n'
        media=self.api.new_media(self.owner,self.project,self.request(filename='restricted.pdf',media_type='application/pdf',size=len(original),sha256=hashlib.sha256(original).hexdigest()))
        self.api.put_media_chunk(self.owner,self.project,media['id'],0,original)
        self.api.complete_media(self.owner,self.project,media['id'],self.request())
        self.error(403,self.api.get_media,accountant,self.project,media['id'])
        self.error(403,self.api.media_source,accountant,self.project,media['id'])
        self.assertEqual(self.api.list_media(accountant,self.project),[])

    def test_invalid_json_numbers_and_unpaired_unicode_never_create_receipts_or_rows(self):
        for title in ('\ud800',float('nan')):
            body=self.request(title=title,work='Synthetic')
            self.error(400,self.api.save_entry,self.tech,self.project,'diary',body)
            self.assertIsNone(self.office.db.execute('SELECT 1 FROM business_operations_requests WHERE request_id=?',(body['request_id'],)).fetchone())
        self.assertEqual(self.api.list_entries(self.owner,self.project,'diary'),[])

if __name__ == '__main__':
    unittest.main()
