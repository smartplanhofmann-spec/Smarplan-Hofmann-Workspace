"""Synthetic subject workflows, private-copy retention and independent restore."""
from datetime import datetime,timedelta,timezone
import io
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid
import zipfile

from core import Office,Problem
import business_schema
from business_foundation import BusinessFoundation
from business_privacy_cases import PrivacyCases,validate_integrity
from privacy_case_sources import MANUAL_AREAS


def request(**values):return dict(request_id=uuid.uuid4().hex,**values)


class PrivacyCasesTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='synthetic-private-case-');self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.path=self.root/'live.db'
        self.office=Office(self.path);self.addCleanup(lambda:self.office.db.close())
        self.owner=dict(id=self.office.add_user('privacy-owner@example.test','Synthetic-password-123','owner'),role='owner')
        self.other=dict(id=self.office.add_user('privacy-manager@example.test','Synthetic-password-123','manager'),role='manager')
        self.foundation=BusinessFoundation(self.office)
        self.customer=self.foundation.save_contact(self.owner,request(name='Synthetic private subject',email='private-person@example.test',notes='PRIVATE-SUBJECT-NOTE',entity_type='person'))
        self.now=datetime(2026,11,3,12,tzinfo=timezone.utc)
        self.api=PrivacyCases(self.office,clock=lambda:self.now)

    def problem(self,status,method,*args,**kwargs):
        with self.assertRaises(Problem) as failure:method(*args,**kwargs)
        self.assertEqual(failure.exception.status,status,failure.exception.message)

    def create(self,kind='export',**changes):
        body=request(id=uuid.uuid4().hex,subject_kind='customer',subject_id=self.customer['id'],request_kind=kind,
            received_date='2026-11-03',due_date='2026-12-03',assigned_to=self.owner['id'],scope='Synthetic requested subject scope',
            retain_until='2026-11-03',retention_reason='Synthetic purpose-specific temporary working-copy review')
        body.update(changes)
        return self.api.create(self.owner,body),body

    def act(self,case,operation,**fields):
        return getattr(self.api,operation)(self.owner,case['id'],request(revision=case['revision'],**fields))['case']

    def verified(self,kind='export'):
        case,_=self.create(kind)
        return self.act(case,'identity',method='existing_contact_channel',evidence='Existing contact independently verified; no identity-document copy',confirmed=True)

    def reviewed(self,kind='export',decision='include'):
        return self.review_all(self.verified(kind),decision)

    def review_all(self,case,decision='include'):
        kind=case['request_kind'];case=self.act(case,'scan')
        for source in case['inventory']['sources']:
            choose='erase_master' if kind=='erasure' and source['table']=='customers' else decision
            case=self.act(case,'review',source_key=source['key'],source_sha256=source['sha256'],decision=choose,
                reason='Reviewed precise subject binding and third-party fields',redacted_value=None,include_originals=False)
        for area in MANUAL_AREAS:
            case=self.act(case,'manual',area=area,decision='checked',evidence='Synthetic bounded fixture: reviewed '+area)
        return case

    def export(self,case):
        body=request(revision=case['revision'],expires_on='2026-11-03',confirmed=True)
        value=self.api.export(self.owner,case['id'],body)
        return value['case'],value['receipt']['export_id'],body

    def checkpoint(self):
        key=self.root/'independent.key';key.write_bytes(b'p'*32);key.chmod(0o600)
        environment=patch.dict(os.environ,{'SMARTPLAN_PRIVACY_CHECKPOINT_FILE':str(self.root/'independent.json'),
            'SMARTPLAN_PRIVACY_CHECKPOINT_KEY_FILE':str(key),'SMARTPLAN_PRIVACY_INSTALLATION_ID':'f'*32})
        environment.start();self.addCleanup(environment.stop)
        business_schema.initialize_privacy_checkpoint(self.office)

    def test_identity_manual_sources_and_real_bounded_export_with_reference_only_receipts(self):
        case,_=self.create()
        self.problem(409,self.api.scan,self.owner,case['id'],request(revision=case['revision']))
        case=self.reviewed()
        case,export_id,command=self.export(case)
        raw=self.api.download(self.owner,case['id'],export_id)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            value=json.loads(archive.read('subject-data.json'))
        self.assertFalse(value['automatic_completeness']);self.assertEqual(value['subject_id'],self.customer['id'])
        self.assertIn('private-person@example.test',json.dumps(value))
        self.assertEqual(self.api.export(self.owner,case['id'],command)['receipt']['export_id'],export_id)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_privacy_case_exports').fetchone()[0],1)
        for table in ('business_privacy_case_events','business_privacy_case_exports','business_privacy_case_requests','audit'):
            dumped=json.dumps([dict(row) for row in self.office.db.execute('SELECT * FROM '+table)])
            self.assertNotIn(self.customer['email'],dumped);self.assertNotIn('PRIVATE-SUBJECT-NOTE',dumped)
        self.assertTrue(validate_integrity(self.office))

    def test_private_assignment_and_fresh_subject_permissions(self):
        project=self.office.add_project(self.owner,'Assigned privacy project',customer_id=self.customer['id'])
        self.office.assign(self.owner,project,self.other['id'])
        case,_=self.create()
        self.problem(403,self.api.view,self.other,case['id'])
        self.foundation.save_grant(self.owner,request(user_id=self.other['id'],permission='privacy.manage',scope='*',effect='allow',revision=0))
        self.problem(404,self.api.view,self.other,case['id'])
        case=self.act(case,'manage',due_date=case['due_date'],assigned_to=self.other['id'],retain_until=case['retain_until'],
            retention_reason=case['retention_reason'],legal_hold=False,reason='Assign active privacy handler',notification_evidence='')
        self.assertEqual(self.api.view(self.other,case['id'])['id'],case['id'])
        self.foundation.save_grant(self.owner,request(user_id=self.other['id'],permission='contacts.read',scope='*',effect='deny',revision=0))
        self.problem(403,self.api.view,self.other,case['id'])

    def test_changed_and_new_sources_require_new_review_and_unknown_table_fails_closed(self):
        case=self.reviewed()
        self.foundation.save_contact(self.owner,request(revision=self.customer['revision'],email='changed@example.test'),self.customer['id'])
        self.problem(409,self.api.export,self.owner,case['id'],request(revision=case['revision'],expires_on='2026-11-03',confirmed=True))
        case=self.act(case,'scan')
        self.assertEqual(case['manual_reviews'],{})
        self.office.db.execute('CREATE TABLE unexpected_personal_copy(id TEXT PRIMARY KEY,private_text TEXT)')
        self.problem(409,self.api.sources,self.owner,case['id'])

    def test_new_linked_project_cannot_hide_behind_previously_reviewed_sources(self):
        case=self.reviewed()
        self.office.add_project(self.owner,'New synthetic project',customer_id=self.customer['id'])
        self.problem(409,self.api.export,self.owner,case['id'],request(revision=case['revision'],expires_on='2026-11-03',confirmed=True))

    def test_contact_correction_uses_current_version_and_preserves_case_history(self):
        case=self.verified('rectification')
        self.problem(409,self.api.correct,self.owner,case['id'],request(revision=case['revision'],source_revision=0,changes={'email':'corrected@example.test'},reason='Verified correction',confirmed=True))
        case=self.act(case,'correct',source_revision=self.customer['revision'],changes={'email':'corrected@example.test'},reason='Verified correction',confirmed=True)
        self.assertEqual(self.foundation.contact(self.owner,self.customer['id'])['email'],'corrected@example.test')
        self.assertEqual(case['actions'][-1]['kind'],'contact_rectified');self.assertIsNone(case['inventory'])
        self.assertTrue(validate_integrity(self.office))

    def test_actual_contact_erasure_requires_external_checkpoint_and_preserves_case_purpose(self):
        case=self.reviewed('erasure')
        case=self.act(case,'erase',contact_revision=self.customer['revision'],reason='Independent review of isolated contact',confirmed=True)
        self.assertEqual(case['actions'][-1]['result']['status'],'blocked')
        self.checkpoint()
        case=self.review_all(case)
        case=self.act(case,'erase',contact_revision=self.customer['revision'],reason='Checkpoint now configured',confirmed=True)
        self.assertEqual(case['actions'][-1]['result']['status'],'erased')
        self.assertEqual(self.foundation.contact(self.owner,self.customer['id'])['email'],'')
        self.assertEqual(case['actions'][-1]['scope'],'contact_master_only')
        self.assertTrue(validate_integrity(self.office))

    def test_financial_or_project_history_blocks_erasure_despite_manual_decision(self):
        self.office.add_project(self.owner,'Retained synthetic project',customer_id=self.customer['id'])
        case=self.reviewed('erasure',decision='retain');self.checkpoint()
        case=self.act(case,'erase',contact_revision=self.customer['revision'],reason='Review remaining legal history',confirmed=True)
        self.assertEqual(case['actions'][-1]['result']['status'],'blocked')
        self.assertTrue(case['actions'][-1]['result']['blockers'])
        self.assertEqual(self.foundation.contact(self.owner,self.customer['id'])['email'],self.customer['email'])

    def test_export_expiry_checkpointed_purge_and_old_backup_do_not_reanimate(self):
        self.checkpoint();case=self.reviewed();case,export_id,_=self.export(case)
        older=sqlite3.connect(self.root/'older.db');older.row_factory=sqlite3.Row;self.addCleanup(older.close)
        self.office.db.backup(older)
        command=request(revision=case['revision'],confirmed=True,reason='Temporary exported copy revoked after supervised review')
        self.api.purge(self.owner,case['id'],command,export_id=export_id)
        self.problem(410,self.api.download,self.owner,case['id'],export_id)
        with self.assertRaises(sqlite3.DatabaseError):
            with self.office.db:self.office.db.execute('INSERT INTO business_privacy_case_export_blobs(export_id,content) VALUES(?,?)',(export_id,b'reintroduced private data'))
        self.api.purge(self.owner,case['id'],command,export_id=export_id)
        restored=SimpleNamespace(db=older,lock=threading.RLock())
        self.assertEqual(older.execute('SELECT COUNT(*) FROM business_privacy_case_export_blobs').fetchone()[0],1)
        business_schema.privacy_restore_guard(restored)
        self.assertEqual(older.execute('SELECT COUNT(*) FROM business_privacy_case_export_blobs').fetchone()[0],0)
        self.assertGreater(older.execute('SELECT COUNT(*) FROM business_privacy_case_contents').fetchone()[0],0)
        self.assertTrue(validate_integrity(restored))
        self.assertNotIn(self.customer['email'],(self.root/'independent.json').read_text())

    def test_case_purge_requires_completion_retention_and_checkpoint_and_survives_restore(self):
        case=self.verified()
        self.problem(409,self.api.purge,self.owner,case['id'],request(revision=case['revision'],confirmed=True,reason='Too early'))
        case=self.act(case,'close',outcome='refused',response_date='2026-11-03',response_evidence='Synthetic response handed over personally',reason='Synthetic disputed scope, recorded response',confirmed=True)
        self.now+=timedelta(days=1)
        command=request(revision=case['revision'],confirmed=True,reason='Purpose expired after documented conclusion')
        self.problem(409,self.api.purge,self.owner,case['id'],command)
        self.checkpoint()
        older=sqlite3.connect(self.root/'older-case.db');older.row_factory=sqlite3.Row;self.addCleanup(older.close);self.office.db.backup(older)
        result=self.api.purge(self.owner,case['id'],command)
        self.assertTrue(result['case']['purged'])
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_privacy_case_contents').fetchone()[0],0)
        self.assertGreater(self.office.db.execute('SELECT COUNT(*) FROM business_privacy_case_events').fetchone()[0],0)
        restored=SimpleNamespace(db=older,lock=threading.RLock())
        business_schema.privacy_restore_guard(restored)
        self.assertEqual(older.execute('SELECT COUNT(*) FROM business_privacy_case_contents').fetchone()[0],0)
        self.assertTrue(validate_integrity(restored))

    def test_identity_failure_can_be_refused_without_falsely_asserting_verification(self):
        case,_=self.create()
        case=self.act(case,'close',outcome='refused',response_date='2026-11-03',response_evidence='Recorded request for identity verification unanswered',reason='Identity could not be verified',confirmed=True)
        self.assertIsNone(case['identity']);self.assertEqual(case['status'],'closed')

    def test_private_blob_updates_and_unproven_deletions_are_blocked(self):
        self.create()
        for statement in ('UPDATE business_privacy_case_contents SET content=content','DELETE FROM business_privacy_case_contents',
            'DELETE FROM business_privacy_case_events','UPDATE business_privacy_case_events SET revision=revision'):
            with self.assertRaises(sqlite3.DatabaseError):
                with self.office.db:self.office.db.execute(statement)

    def test_command_status_has_only_own_reference_with_fresh_permissions(self):
        case,command=self.create()
        proof=self.api.command_status(self.owner,case['id'],command['request_id'])
        self.assertTrue(proof['confirmed']);self.assertEqual(proof['reference'],{'case_id':case['id']})
        self.assertNotIn(self.customer['email'],json.dumps(proof));self.assertNotIn('scope',proof)
        self.problem(404,self.api.command_status,self.owner,case['id'],uuid.uuid4().hex)
        self.problem(403,self.api.command_status,self.other,case['id'],command['request_id'])
        with self.office.db:self.office.db.execute('UPDATE users SET active=0 WHERE id=?',(self.owner['id'],))
        self.problem(401,self.api.command_status,self.owner,case['id'],command['request_id'])

    def test_subject_options_follow_scope_and_do_not_expose_security_or_payroll(self):
        options=self.api.options(self.owner,'private subject')
        self.assertEqual(options['subjects'],[{'kind':'customer','id':self.customer['id'],'label':self.customer['name']}])
        self.foundation.save_grant(self.owner,request(user_id=self.other['id'],permission='privacy.manage',scope='*',effect='allow',revision=0))
        delegated=self.api.options(self.other)
        self.assertEqual(delegated['subjects'],[])
        self.assertEqual([v['id'] for v in delegated['handlers']],[self.other['id']])

    def test_employee_sources_and_export_need_fresh_personnel_permission(self):
        from business_planning import Planning
        employee=Planning(self.office).save_employee(self.owner,request(user_id=self.other['id'],name='Synthetic employee subject'))
        case,_=self.create(subject_kind='employee',subject_id=employee['id'])
        case=self.act(case,'identity',method='in_person',evidence='Synthetic employee personally verified',confirmed=True)
        case=self.review_all(case)
        self.assertIn('business_employees',{source['table'] for source in case['inventory']['sources']})
        case,export_id,_=self.export(case)
        with zipfile.ZipFile(io.BytesIO(self.api.download(self.owner,case['id'],export_id))) as archive:
            data=json.loads(archive.read('subject-data.json'))
        account=[item['data'] for item in data['data'] if item['source']['table']=='users'][0]
        self.assertNotIn('password',account);self.assertNotIn('salt',account)
        for permission in ('privacy.manage','personnel.read','personnel.export'):
            self.foundation.save_grant(self.owner,request(user_id=self.other['id'],permission=permission,scope='*',effect='allow',revision=0))
        case,_=self.create(subject_kind='employee',subject_id=employee['id'],assigned_to=self.other['id'])
        def delegated(case,operation,**fields):
            return getattr(self.api,operation)(self.other,case['id'],request(revision=case['revision'],**fields))['case']
        case=delegated(case,'identity',method='in_person',evidence='Delegated employee verification',confirmed=True)
        case=delegated(case,'scan')
        self.assertIn('users',case['inventory']['blocked_tables'])
        for source in case['inventory']['sources']:
            case=delegated(case,'review',source_key=source['key'],source_sha256=source['sha256'],decision='include',
                reason='Reviewed delegated personnel source',redacted_value=None,include_originals=False)
        for area in MANUAL_AREAS:
            case=delegated(case,'manual',area=area,decision='checked',evidence='Bounded delegated fixture '+area)
        exported=self.api.export(self.other,case['id'],request(revision=case['revision'],expires_on='2026-11-03',confirmed=True))
        case=exported['case'];export_id=exported['receipt']['export_id']
        self.assertTrue(self.api.download(self.other,case['id'],export_id).startswith(b'PK'))
        self.foundation.save_grant(self.owner,request(user_id=self.other['id'],permission='personnel.export',scope='*',effect='deny',revision=1))
        self.problem(403,self.api.download,self.other,case['id'],export_id)
        self.assertEqual(self.api.view(self.other,case['id'])['id'],case['id'])
        self.foundation.save_grant(self.owner,request(user_id=self.other['id'],permission='personnel.read',scope='*',effect='deny',revision=1))
        self.problem(403,self.api.view,self.other,case['id'])

    def test_user_export_never_returns_authentication_bytes_as_selected_originals(self):
        from privacy_case_sources import inventory,resolve
        # SQLite accepts binary password/salt values. Even this storage variation
        # cannot turn an explicitly omitted secret into a selectable original.
        with self.office.db:
            self.office.db.execute('UPDATE users SET salt=?,password=? WHERE id=?',(b'SYNTHETIC-SALT',b'SYNTHETIC-PASSWORD',self.other['id']))
        sources=inventory(self.office,self.owner,'user',self.other['id'])
        descriptor=next(source for source in sources['sources'] if source['table']=='users')
        value,originals=resolve(self.office,self.owner,descriptor,export=True)
        self.assertNotIn('password',value);self.assertNotIn('salt',value)
        self.assertNotIn('password',originals);self.assertNotIn('salt',originals)

    def test_bank_source_inventory_needs_all_current_financial_rights(self):
        from privacy_case_sources import access
        for permission in ('privacy.manage','bank.read','accounting.read','finance.read'):
            self.foundation.save_grant(self.owner,request(user_id=self.other['id'],permission=permission,scope='*',effect='allow',revision=0))
        access(self.office,self.other,'business_bank_statements')
        for permission in ('bank.read','accounting.read','finance.read'):
            self.foundation.save_grant(self.owner,request(user_id=self.other['id'],permission=permission,scope='*',effect='deny',revision=1))
            self.problem(403,access,self.office,self.other,'business_bank_statements')
            self.foundation.save_grant(self.owner,request(user_id=self.other['id'],permission=permission,scope='*',effect='allow',revision=2))

    def test_purchase_receipt_metadata_requires_actual_order_project_and_inventory_rights(self):
        from test_business_purchase_changes import PurchaseChangesTests
        from privacy_case_sources import access
        fixture=PurchaseChangesTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.apply('amendments',fixture.amendment('12'))
        fixture.receive(expected_amendment_revision=1)
        source=dict(fixture.office.db.execute('SELECT * FROM business_purchase_receipt_terms').fetchone())
        fixture.grant(fixture.tech,'privacy.manage','finance.read')
        access(fixture.office,fixture.tech,'business_purchase_receipt_terms',source)
        foundation=BusinessFoundation(fixture.office)
        foundation.save_grant(fixture.owner,request(user_id=fixture.tech['id'],permission='inventory.read',scope='*',effect='deny',revision=0))
        self.problem(403,access,fixture.office,fixture.tech,'business_purchase_receipt_terms',source)
        foundation.save_grant(fixture.owner,request(user_id=fixture.tech['id'],permission='inventory.read',scope='*',effect='allow',revision=1))
        fixture.grant(fixture.outsider,'privacy.manage','finance.read','inventory.read')
        self.problem(404,access,fixture.office,fixture.outsider,'business_purchase_receipt_terms',source)

    def test_resource_source_requires_planning_scope_and_keeps_conservative_raw_access(self):
        from privacy_case_sources import access
        self.foundation.save_grant(self.owner,request(user_id=self.other['id'],permission='privacy.manage',scope='*',effect='allow',revision=0))
        # Manager has planning read/write, but unrestricted raw resource snapshots
        # remain deliberately owner-only even with the case permission.
        self.problem(403,access,self.office,self.other,'business_resource_handoffs')
        access(self.office,self.owner,'business_resource_handoffs')


if __name__=='__main__':unittest.main()
