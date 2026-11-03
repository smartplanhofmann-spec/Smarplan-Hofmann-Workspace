"""Real isolated DB snapshots, original bytes, credentials and exit evidence."""
import base64
from concurrent.futures import ThreadPoolExecutor
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs,urlsplit
import uuid
import zipfile

from cryptography.fernet import Fernet
import test_business_accounting_components as fixture
from business_company_handover import CompanyHandover,CHECKS,validate_integrity,dispatch,schema_statements,guard_statements
from business_customer_workspace import CustomerWorkspace
from company_export_archive import verify,sha
from core import Problem,canonical
from online.instance import bind
from online.storage import Storage


class CompanyHandoverTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.ComponentTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.office,self.owner=self.f.office,self.f.owner
        self.temp=tempfile.TemporaryDirectory(prefix='synthetic-company-handover-');self.addCleanup(self.temp.cleanup)
        # Allows this focused test to run before the central additive registry
        # hook is merged; normal production initialization uses that registry.
        with self.office.db:
            for statement in schema_statements('BLOB')+guard_statements('sqlite'):self.office.db.execute(statement)
        self.key=Fernet.generate_key();self.instance=uuid.uuid4().hex
        self.storage=Storage(self.office,self.key,'handover.example.test',config={'server':{'path':str(Path(self.temp.name)/'company')}})
        bind(self.office,self.instance,'handover.example.test',self.key,self.storage)
        self.api=CompanyHandover(self.office,clock=self.f.clock)

    def command(self,**changes):
        state=self.api.state(self.owner)
        return dict(request_id=uuid.uuid4().hex,instance_id=self.instance,catalog_sha256=state['catalog_sha256'],reason='Synthetic documented company handover',confirmation=True,sensitive_data_confirmed=True)|changes

    def archive(self):
        command=self.command();result=self.api.create(self.owner,command)
        raw=bytes(self.api.exported(self.owner,result['id'],action='archive'))
        return result,raw,command

    def rows(self,archive,table):
        return [json.loads(line) for line in archive.read('data/'+table+'.jsonl').splitlines()]

    def test_originals_audit_relationships_quarantine_and_no_authentication_material(self):
        invoice=self.f.invoice();receipt=self.f.receipt()
        self.office.portal_origin='https://handover.example.test'
        portal=CustomerWorkspace(self.office)
        grant=portal.create_grant(self.owner,dict(request_id=uuid.uuid4().hex,project_id=self.f.project,customer_id=self.f.customer,
            recipient_name='Synthetic customer',recipient_email='handover-customer@example.test',expires_in_days=7,allow_upload=True,confirmation=True))
        secret=parse_qs(urlsplit(grant['portal_url']).fragment)['key'][0]
        token=portal.open_session(grant['grant']['id'],secret)['token']
        original=b'%PDF-1.4\nSynthetic quarantined original\n%%EOF'
        uploaded=portal.upload(token,dict(request_id=uuid.uuid4().hex,filename='private-original.pdf',media_type='application/pdf',size=len(original),sha256=sha(original),content_base64=base64.b64encode(original).decode(),note='Unreviewed customer original'))
        ciphertext=Fernet(self.key).encrypt(b'synthetic provider password').decode()
        with self.office.db:
            self.office.db.execute('INSERT INTO secrets VALUES(?,?)',('synthetic.export.secret',ciphertext))
            self.office.db.execute('INSERT INTO sessions VALUES(?,?,?)',('synthetic-active-login',self.owner['id'],9999999999))
        stored_password=self.office.db.execute('SELECT password FROM users WHERE id=?',(self.owner['id'],)).fetchone()[0]
        result,raw,command=self.archive()
        self.assertEqual(self.api.create(self.owner,command),result)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            manifest=json.loads(archive.read('manifest.json'))
            all_bytes=b''.join(archive.read(name) for name in archive.namelist())
            for denied in (secret,sha(secret),token,sha(token),ciphertext,stored_password,'synthetic-active-login'):
                self.assertNotIn(denied.encode(),all_bytes)
            self.assertNotIn('data/secrets.jsonl',archive.namelist())
            self.assertNotIn('data/business_customer_staff_requests.jsonl',archive.namelist())
            row=next(row for row in self.rows(archive,'business_customer_uploads') if row['id']==uploaded['id'])
            self.assertEqual(archive.read(row['original']['$file']),original)
            self.assertEqual(self.rows(archive,'business_customer_acceptances'),[])
            frozen=next(row for row in self.rows(archive,'business_document_archives') if row['document_id']==invoice['id'])
            self.assertEqual(archive.read(frozen['pdf']['$file']),self.f.docs.archive(self.owner,invoice['id'],'pdf'))
            receipt_row=next(row for row in self.rows(archive,'business_incoming_receipts') if row['id']==receipt['id'])
            expected=bytes(self.office.db.execute('SELECT original FROM business_incoming_receipts WHERE id=?',(receipt['id'],)).fetchone()[0])
            self.assertEqual(archive.read(receipt_row['original']['$file']),expected)
            self.assertTrue(self.rows(archive,'audit'))
            self.assertTrue(any(row['relationships'] for row in manifest['inventory']))
            self.assertTrue(all(row['retention_days'] is None for row in manifest['inventory']))
            payroll=next(row for row in manifest['inventory'] if row['table']=='business_payroll_account_events')
            self.assertEqual(payroll['retention_rule']['trigger'],'last_recorded_wage_payment_date')
            self.assertEqual(payroll['retention_rule']['example']['retain_through'],'2032-12-31')
            personnel=next(row for row in manifest['inventory'] if row['table']=='business_personnel_files')
            self.assertNotIn('retention_rule',personnel)
            self.assertFalse(manifest['database_restore_supported']);self.assertFalse(manifest['technical_request_replay_included'])
        self.assertTrue(verify(raw,instance_id=self.instance)['valid'])
        self.assertTrue(validate_integrity(self.office))

    def test_future_schema_is_fail_closed_and_never_silently_partial(self):
        with self.office.db:self.office.db.execute('CREATE TABLE future_company_data(id TEXT,api_key TEXT)')
        self.assertFalse(self.api.state(self.owner)['ready'])
        with self.assertRaises(Problem) as failure:self.api.create(self.owner,self.command())
        self.assertEqual(failure.exception.status,409);self.assertEqual(failure.exception.request_resolution,'not_accepted')
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_company_exports').fetchone()[0],0)
        with self.office.db:
            self.office.db.execute('DROP TABLE future_company_data')
            self.office.db.execute('ALTER TABLE users ADD COLUMN new_credential TEXT')
        self.f.problem(409,self.api.create,self.owner,self.command())

    def test_chunked_plan_original_and_private_personnel_file_are_portable(self):
        from online.plan_imports import PlanImports,ensure_sqlite_schema,CHUNK_SIZE
        from business_planning import Planning
        from business_personnel_workflow import PersonnelWorkflow
        ensure_sqlite_schema(self.office);plans=PlanImports(self.office)
        original=b'%PDF-1.4\n'+b'synthetic source '*20000
        with self.office.lock,self.office.db:
            source=plans.create(self.owner,self.f.project,dict(request_id=uuid.uuid4().hex,filename='original-plan.pdf',media_type='application/pdf',size=len(original),sha256=sha(original),page=0,title='Synthetic plan source'))
            for index,offset in enumerate(range(0,len(original),CHUNK_SIZE)):
                plans.put_chunk(self.owner,self.f.project,source['id'],index,original[offset:offset+CHUNK_SIZE])
            plans.complete_upload(self.owner,self.f.project,source['id'])
            partial=plans.create(self.owner,self.f.project,dict(request_id=uuid.uuid4().hex,filename='unfinished.pdf',media_type='application/pdf',size=100,sha256='a'*64,page=0,title='Explicit unfinished upload'))
            employee=Planning(self.office).save_employee(self.owner,dict(request_id=uuid.uuid4().hex,user_id=self.f.tech['id'],name='Synthetic employee',weekly_minutes=2400,hourly_cost_minor=2500))
        private=b'%PDF-1.4\nSynthetic private personnel evidence\n%%EOF'
        person=PersonnelWorkflow(self.office).upload(self.owner,dict(request_id=uuid.uuid4().hex,employee_id=employee['id'],purpose='personnel',owner_visible=False,
            filename='private-personnel.pdf',media_type='application/pdf',content_base64=base64.b64encode(private).decode()))
        result,raw,unused=self.archive()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            manifest=json.loads(archive.read('manifest.json'))
            assembled=next(value for value in manifest['originals'] if value['id']==source['id'])
            self.assertTrue(assembled['complete']);self.assertEqual(archive.read(assembled['path']),original)
            self.assertFalse(next(value for value in manifest['originals'] if value['id']==partial['id'])['complete'])
            row=next(value for value in self.rows(archive,'business_personnel_files') if value['id']==person['id'])
            self.assertEqual(archive.read(row['original']['$file']),private)
        self.assertTrue(verify(raw,instance_id=self.instance)['valid'])

    def test_migration_source_files_are_exact_sensitive_originals_and_corruption_blocks_export(self):
        import business_migrations
        package_id,file_id=uuid.uuid4().hex,uuid.uuid4().hex
        original=b'source_id,name,notes\nlegacy-1,Synthetic person,Confidential source evidence\n'
        payload=dict(id=package_id,source_system='other',source_account='synthetic-export',label='Historical CRM original',
            scope='Explicit original file only',period_from=None,period_to=None,created_by=self.owner['id'],created_at=self.api.now())
        with self.office.db:
            for statement in business_migrations.schema_statements('BLOB')+business_migrations.guard_statements('sqlite'):
                self.office.db.execute(statement)
            self.office.db.execute('INSERT INTO business_migration_packages VALUES(?,?,?,?,?)',
                (package_id,canonical(payload),business_migrations.sha(payload),self.owner['id'],self.api.now()))
            self.office.db.execute('INSERT INTO business_migration_files VALUES(?,?,?,?,?,?,?,?)',
                (file_id,package_id,'legacy-contacts.csv','text/csv',original,sha(original),self.owner['id'],self.api.now()))
        unused,raw,unused=self.archive()
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            row=self.rows(archive,'business_migration_files')[0]
            self.assertEqual(archive.read(row['content']['$file']),original)
            self.assertNotIn('data/business_migration_requests.jsonl',archive.namelist())
            inventory=json.loads(archive.read('manifest.json'))['inventory']
            self.assertTrue(next(value for value in inventory if value['table']=='business_migration_files')['sensitive'])
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_migration_files_update_guard')
            self.office.db.execute('UPDATE business_migration_files SET content=? WHERE id=?',(b'Changed source',file_id))
        with self.assertRaises(Problem) as failure:self.api.create(self.owner,self.command())
        self.assertEqual(failure.exception.status,409);self.assertEqual(failure.exception.request_resolution,'not_accepted')

    def test_foreign_binding_fresh_owner_and_offline_or_project_user_cannot_export(self):
        result,raw,command=self.archive()
        self.f.problem(403,self.api.create,self.f.tech,command)
        self.f.problem(403,self.api.exported,self.f.other_actor,result['id'])
        self.f.problem(409,self.api.create,self.owner,dict(command,instance_id=uuid.uuid4().hex))
        with self.assertRaises(ValueError):verify(raw,instance_id=uuid.uuid4().hex)
        with self.office.db:self.office.db.execute("UPDATE users SET role='manager' WHERE id=?",(self.owner['id'],))
        self.f.problem(403,self.api.create,self.owner,command)
        self.f.problem(403,self.api.exported,self.owner,result['id'])

    def test_lost_ack_parallel_same_request_returns_one_immutable_archive(self):
        command=self.command()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.api.create(self.owner,command),range(2)))
        self.assertEqual(results[0],results[1]);self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_company_exports').fetchone()[0],1)
        self.f.problem(409,self.api.create,self.owner,dict(command,reason='Changed original request'))
        with self.assertRaises(sqlite3.IntegrityError):self.office.db.execute('DELETE FROM business_company_exports')
        raw=bytes(self.api.exported(self.owner,results[0]['id'],action='archive'))
        self.office.add_project(self.owner,'Later business change','Later customer')
        self.assertEqual(bytes(self.api.exported(self.owner,results[0]['id'],action='archive')),raw)

    def test_exit_review_is_explicit_versioned_evidence_and_changes_no_access(self):
        result,raw,unused=self.archive()
        before=self.f.snapshot(('users','sessions','plan_sessions','secrets','business_portal_revocations','business_customer_revocations'))
        body=dict(request_id=uuid.uuid4().hex,instance_id=self.instance,expected_revision=0,export_id=result['id'],export_sha256=result['sha256'],
            checks={name:False for name in CHECKS},evidence='Synthetic receiver and retention decision references',reason='Prepare exit review',confirmation=True)
        first=self.api.review(self.owner,body);self.assertEqual(first['status'],'in_progress')
        self.assertEqual(self.api.review(self.owner,body),first)
        next_body=dict(body,request_id=uuid.uuid4().hex,expected_revision=1,checks={name:True for name in CHECKS})
        latest=self.api.review(self.owner,next_body);self.assertEqual(latest['status'],'ready_for_operator_review')
        self.assertFalse(latest['deletion_executed']);self.assertFalse(latest['revocations_executed'])
        self.assertEqual(self.f.snapshot(tuple(before)),before)
        self.assertTrue(validate_integrity(self.office))
        self.f.problem(409,self.api.review,self.owner,dict(next_body,request_id=uuid.uuid4().hex))

    def test_size_limit_and_audit_failure_roll_back_complete_export_atomically(self):
        command=self.command()
        with patch('company_export_archive.MAX_SOURCE_BYTES',1):self.f.problem(413,self.api.create,self.owner,command)
        with patch.object(self.office,'audit',side_effect=RuntimeError('Synthetic transaction interruption')):
            with self.assertRaises(RuntimeError):self.api.create(self.owner,command)
        for table in ('business_company_exports','business_company_handover_requests'):
            self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0)
        self.assertTrue(self.api.create(self.owner,command)['size']>0)

    def test_archive_verifier_rejects_missing_changed_duplicate_and_unsafe_members(self):
        unused,raw,unused=self.archive()
        def altered(change):
            output=io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(raw)) as source,zipfile.ZipFile(output,'w') as dest:
                for item in source.infolist():
                    content=source.read(item.filename)
                    if item.filename=='data/projects.jsonl':content=content.replace(b'Synthetic project',b'Altered project')
                    dest.writestr(item.filename,content)
                if change:dest.writestr(change,b'Unexpected data')
            return output.getvalue()
        for change in ('','../escape.txt','README.txt'):
            with self.subTest(change=change),self.assertRaises(ValueError):verify(altered(change),instance_id=self.instance)

    def test_strict_transport_and_sensitive_confirmation(self):
        for change in ({'confirmation':False},{'sensitive_data_confirmed':False},{'secret':'unexpected'}):
            self.f.problem(400,self.api.create,self.owner,self.command(**change))
        self.f.problem(400,dispatch,self.office,self.owner,'/company-handover','GET',{'_query':{'instance_id':'foreign'}})
        self.f.problem(405,dispatch,self.office,self.owner,'/company-handover','POST',{})

    def test_distributed_verifier_reopens_archive_without_application_or_database(self):
        result,raw,unused=self.archive();target=Path(self.temp.name)
        package=target/'company.zip';package.write_bytes(raw)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            # This script is generated locally by our trusted producer, never
            # downloaded or executed from an untrusted received archive.
            script=target/'verify_archive.py';script.write_bytes(archive.read('verify_archive.py'))
        completed=subprocess.run([sys.executable,'-I',str(script),str(package),'--instance-id',self.instance],cwd=self.temp.name,
            capture_output=True,text=True,check=True)
        proof=json.loads(completed.stdout)
        self.assertEqual(proof['sha256'],result['sha256']);self.assertTrue(proof['valid'])
        foreign=subprocess.run([sys.executable,'-I',str(script),str(package),'--instance-id',uuid.uuid4().hex],cwd=self.temp.name,
            capture_output=True,text=True)
        self.assertNotEqual(foreign.returncode,0);self.assertEqual(sorted(value.name for value in target.glob('*') if value.is_file()),['company.zip','verify_archive.py'])

    def test_self_consistent_zip_still_requires_matching_inventory_and_original_descriptors(self):
        unused,raw,unused=self.archive()
        def altered(change):
            output=io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(raw)) as source,zipfile.ZipFile(output,'w') as dest:
                manifest=json.loads(source.read('manifest.json'));change(manifest)
                for item in source.infolist():
                    dest.writestr(item.filename,canonical(manifest).encode() if item.filename=='manifest.json' else source.read(item.filename))
            return output.getvalue()
        changes=(lambda m:m['inventory'][0].update(row_count=-1),
                 lambda m:m['tables'][0].update(columns=['invented_column']),
                 lambda m:m['inventory'].append(m['inventory'][0]),
                 lambda m:m.update(export_id='foreign'),
                 lambda m:m['entries'][0].update(size=True))
        for change in changes:
            with self.subTest(change=change),self.assertRaises(ValueError):verify(altered(change),instance_id=self.instance)

    def test_archive_cannot_be_swapped_between_valid_receipts(self):
        first,unused,unused=self.archive();second,second_raw,unused=self.archive()
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_company_exports_update_guard')
            self.office.db.execute('UPDATE business_company_exports SET archive=?,archive_sha256=?,archive_size=? WHERE id=?',
                (second_raw,second['sha256'],len(second_raw),first['id']))
        with self.assertRaises(Problem) as failure:self.api.exported(self.owner,first['id'],action='archive')
        self.assertEqual(failure.exception.status,409)
        with self.assertRaises(ValueError):validate_integrity(self.office)

    def test_tampered_technical_receipt_cannot_survive_restore_validation(self):
        result,unused,command=self.archive()
        with self.office.db:
            self.office.db.execute('DROP TRIGGER business_company_handover_requests_update_guard')
            self.office.db.execute('UPDATE business_company_handover_requests SET result_json=? WHERE request_id=?',
                (canonical(dict(result,reason='Altered receipt')),command['request_id']))
        with self.assertRaises(ValueError):validate_integrity(self.office)


class BankOriginalExportTests(unittest.TestCase):
    def test_resource_custody_schema_inventory_and_private_original_match_exactly(self):
        import business_resource_custody as module
        from company_export_archive import Builder,_blob
        from company_export_catalog import COLUMNS,policy
        connection=sqlite3.connect(':memory:');self.addCleanup(connection.close)
        for statement in module.schema_statements('BLOB'):connection.execute(statement)
        for table in module.TABLES:
            self.assertEqual([row[1] for row in connection.execute('PRAGMA table_info('+table+')')],COLUMNS[table].split(','))
            item=policy(table);self.assertTrue(item['sensitive']);self.assertIsNone(item['retention_days'])
            self.assertEqual(item['included'],not table.endswith('_requests'))
        original=b'%PDF-1.4\nSynthetic employee resource handoff original\n%%EOF'
        builder=Builder();self.addCleanup(builder.zip.close)
        descriptor=_blob(builder,'business_resource_evidence',1,'content',dict(sha256=sha(original),media_type='application/pdf'),original)
        self.assertEqual(builder.zip.read(descriptor['$file']),original)
        with self.assertRaises(Problem):_blob(builder,'business_resource_evidence',2,'content',dict(sha256=sha(original)),original+b'changed')

    def test_original_statement_bytes_use_source_file_hash_and_sensitive_inventory(self):
        from company_export_archive import Builder,_blob
        from company_export_catalog import policy
        original=b'transaction_id;booking_date;amount;counterparty\nsynthetic-1;2026-11-02;-581.29;Synthetic person\n'
        builder=Builder();self.addCleanup(builder.zip.close)
        descriptor=_blob(builder,'business_bank_statements',1,'original',dict(file_sha256=sha(original)),original)
        self.assertEqual(builder.zip.read(descriptor['$file']),original)
        self.assertEqual(descriptor['sha256'],sha(original))
        item=policy('business_bank_statements')
        self.assertTrue(item['included']);self.assertTrue(item['personal_data']);self.assertTrue(item['sensitive'])
        self.assertEqual(item['category'],'financial');self.assertFalse(policy('business_bank_requests')['included'])
        with self.assertRaises(Problem) as failure:
            _blob(builder,'business_bank_statements',2,'original',dict(file_sha256=sha(original)),original+b'changed')
        self.assertEqual(failure.exception.status,409)


if __name__=='__main__':unittest.main()
