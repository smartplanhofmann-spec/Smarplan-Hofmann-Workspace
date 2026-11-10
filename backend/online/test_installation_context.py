"""Installed source marker is distinct from API compatibility and checkout HEAD."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid
from online import test_offline_instance_binding as instances
from online import installation
from business_foundation import BusinessFoundation


class InstallationHttpTests(unittest.TestCase):
    def setUp(self):
        self.f = instances.OfflineInstanceBindingHttpTests('runTest')
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)

    def test_actual_mfa_owner_can_read_unknown_installed_source_without_guessing(self):
        value = self.f.call(self.f.a, '/business/installation').json
        self.assertEqual(value, dict(schema_version=1, status='unrecorded',
            source_commit=None, api_compatibility_version='0.12.0-online-pilot'))

    def test_recorded_source_is_frozen_per_running_app_and_never_comes_from_outer_marker(self):
        for company, commit in ((self.f.a, 'a'*40), (self.f.b, 'b'*40)):
            marker=self.f.root / (commit[:1]+'-BUILD_SOURCE.json')
            installation.write_context(marker, commit)
            with patch.object(installation, 'MARKER', marker):
                self.f.reopen(company)
            marker.write_text(json.dumps(dict(schema_version=1, source_commit='c'*40)))
        for company, commit in ((self.f.a, 'a'*40), (self.f.b, 'b'*40)):
            value=self.f.call(company, '/business/installation').json
            self.assertEqual(value['status'], 'recorded')
            self.assertEqual(value['source_commit'], commit)
            self.assertEqual(set(value), {'schema_version','status','source_commit','api_compatibility_version'})
            health=company['client'].get('/ready',base_url='https://'+company['host']).json
            self.assertEqual(health['version'], '0.12.0-online-pilot')
            self.assertNotIn('source_commit',health)

    def test_current_settings_rights_mfa_token_and_offline_scope_are_required(self):
        company=self.f.a
        self.f.call(company,'/business/installation',token=None,status=401)
        user=self.f.call(company,'/users',dict(email='support-reader@example.test',
            password='Synthetic-support-password-123',role='technician'),status=201).json['id']
        token=self.f.login(company,'support-reader@example.test','Synthetic-support-password-123')
        self.f.call(company,'/business/installation',token=token,status=403)
        foundation=BusinessFoundation(company['office'])
        actor=company['office'].user(company['token'])
        grant=dict(request_id=uuid.uuid4().hex,user_id=user,permission='settings.manage',scope='*',effect='allow',revision=0)
        foundation.save_grant(actor,grant)
        self.f.call(company,'/business/installation',token=token)
        foundation.save_grant(actor,dict(grant,request_id=uuid.uuid4().hex,revision=1,effect='deny'))
        self.f.call(company,'/business/installation',token=token,status=403)
        offline=self.f.grant(company,business=True)
        self.f.call(company,'/business/installation',token=offline['token'],status=403)
        self.f.call(company,'/business/installation',{},status=405)
        self.f.call(company,'/business/installation?path=/etc/passwd',status=400)
        self.f.call(company,'/business/installation',method='GET',raw=b'{}',status=400)


class InstallationMarkerTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory(prefix='synthetic-installed-source-')
        self.addCleanup(directory.cleanup)
        self.root=Path(directory.name)
        self.path=self.root/'BUILD_SOURCE.json'

    def test_packaging_records_only_full_commit_and_refuses_to_overwrite_an_old_release(self):
        installation.write_context(self.path,'a'*40)
        before=self.path.read_bytes()
        self.assertEqual(installation.read_context(self.path)['source_commit'],'a'*40)
        with self.assertRaises(FileExistsError):installation.write_context(self.path,'b'*40)
        self.assertEqual(self.path.read_bytes(),before)
        for commit in ('short',True,'A'*40,'a'*40+'\n','a'*40+' /private/path'):
            target=self.root/uuid.uuid4().hex
            with self.assertRaises(ValueError):installation.write_context(target,commit)
            self.assertFalse(target.exists())

    def test_missing_unsafe_or_ambiguous_marker_never_becomes_an_installed_commit(self):
        unknown=dict(schema_version=1,status='unrecorded',source_commit=None)
        self.assertEqual(installation.read_context(self.path),unknown)
        for raw in (b'{}',b'[]',b'null',b'\xff',b' '*1025,b'['*1024,
                    b'{"schema_version":true,"source_commit":"'+b'a'*40+b'"}',
                    b'{"schema_version":1,"source_commit":"'+b'a'*40+b'","source_commit":"'+b'b'*40+b'"}',
                    json.dumps(dict(schema_version=1,source_commit='a'*40,private_path='/private/source')).encode()):
            self.path.write_bytes(raw)
            self.assertEqual(installation.read_context(self.path),unknown)
        self.path.unlink()
        installation.write_context(self.path,'a'*40)
        self.path.chmod(0o664)
        self.assertEqual(installation.read_context(self.path),unknown)
        self.path.chmod(0o644)
        link=self.root/'linked.json';link.symlink_to(self.path)
        self.assertEqual(installation.read_context(link),unknown)
        self.assertEqual(installation.read_context(self.root),unknown)
        fifo=self.root/'fifo';os.mkfifo(fifo)
        self.assertEqual(installation.read_context(fifo),unknown)


if __name__ == '__main__':
    unittest.main()
