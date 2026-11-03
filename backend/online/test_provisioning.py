"""Synthetic operator manifests: no host services, users or external traffic."""
from dataclasses import replace
import json
import os
import socket
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from online import provisioning as p
from online.instance_roles import InstanceRoles,LEGACY,load,parse,configured
from online.release import validate_dsns
from online import provisioning_host as host


def company(slug='testalpha',**changes):
    value=dict(slug=slug,instance_id='a'*32,public_host=slug+'.example.test',port=18871,
        source_commit='c'*40,privacy_installation_id='b'*32,plan_import=False)
    value.update(changes)
    return p.Company(**value)


class ProvisioningTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='synthetic-company-plan-');self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.company=company()

    def test_exact_manifest_no_untrusted_selector_or_shell_values(self):
        value=self.company.document();self.assertEqual(p.parse(value),self.company)
        for change in ({'port':True},{'slug':'alpha;id'},{'public_host':'evil.test/path'},
                       {'public_host':'office.smartplan-hofmann.de'},{'instance_id':'unknown'},
                       {'source_commit':'main'},{'company_id':'request-selected'},{'port':8766}):
            with self.subTest(change=change),self.assertRaises((ValueError,TypeError)):
                p.parse({**value,**change})

    def test_plan_is_deterministic_has_no_credentials_and_never_activates_publicly(self):
        self.assertEqual(p.plan(self.company),p.plan(self.company))
        self.assertFalse(p.plan(self.company)['public_activation'])
        files=p.render(self.company)
        self.assertEqual(files,p.render(self.company))
        self.assertNotIn(b'PASSWORD',files['service.env'])
        self.assertIn(b'user=sp_testalpha_run',files['service.env'])
        self.assertIn(b'User=sp_testalpha_run',files['smartplan-testalpha-api.service'])
        self.assertIn(b'127.0.0.1:18871',files['smartplan-testalpha-api.service'])
        self.assertNotIn(b'SMARTPLAN_SMTP_',files['service.env'])

    def test_resource_collisions_are_rejected_but_exact_retry_is_allowed(self):
        p.check_inventory(self.company,[self.company])
        beta=company('testbeta',instance_id='d'*32,privacy_installation_id='e'*32,port=18872)
        p.check_inventory(self.company,[beta])
        for field in ('slug','instance_id','public_host','port','privacy_installation_id'):
            with self.subTest(field=field),self.assertRaises(ValueError):
                p.check_inventory(self.company,[replace(beta,**{field:getattr(self.company,field)})])

    def test_bundle_retries_exact_bytes_and_preserves_partial_artifacts(self):
        first=p.write_bundle(self.root,self.company,trusted_root=self.root)
        self.assertEqual(first,p.write_bundle(self.root,self.company,trusted_root=self.root))
        (self.root/'service.env').write_bytes(b'changed')
        with self.assertRaises(ValueError):p.write_bundle(self.root,self.company,trusted_root=self.root)
        self.assertEqual((self.root/'service.env').read_bytes(),b'changed')

    def test_private_operator_umask_does_not_hide_required_runtime_group_configuration(self):
        old=os.umask(0o077)
        try:p._exclusive(self.root/'service.env',b'non-secret fixture',0o640)
        finally:os.umask(old)
        self.assertEqual((self.root/'service.env').stat().st_mode&0o777,0o640)

    def test_bundle_rejects_links_foreign_manifest_and_concurrent_reservation(self):
        (self.root/'service.env').symlink_to(self.root/'outside')
        with self.assertRaises(ValueError):p.write_bundle(self.root,self.company,trusted_root=self.root)
        (self.root/'service.env').unlink()
        with p.reservation(self.root,self.company,trusted_root=self.root):
            with self.assertRaises(BlockingIOError):
                with p.reservation(self.root,self.company,trusted_root=self.root):pass
        with self.assertRaises(ValueError):
            p.write_bundle(self.root,replace(self.company,port=18872),trusted_root=self.root)

    def test_roles_are_immutable_exact_and_never_derived_from_runtime_dsn(self):
        roles=self.company.roles
        self.assertEqual(roles.linux_user,roles.runtime)
        self.assertEqual(parse(roles.document()),roles)
        for change in ({'runtime':'postgres'},{'owner':'other_owner'},{'linux_user':'different'},{'instance_id':''}):
            with self.assertRaises(ValueError):parse({**roles.document(),**change})
        with self.assertRaises(Exception):roles.runtime='postgres'
        with patch.dict(os.environ,{},clear=True):self.assertEqual(configured(),LEGACY)

    def test_protected_role_file_uses_explicit_synthetic_trust_root_without_weakening_production(self):
        path=self.root/'roles.json';path.write_text(json.dumps(self.company.roles.document()));path.chmod(0o600)
        self.assertEqual(load(path,expected_uid=os.getuid(),trusted_root=self.root),self.company.roles)
        if os.getuid()!=0:
            with self.assertRaises(ValueError):load(path)
        path.chmod(0o622)
        with self.assertRaises(ValueError):load(path,expected_uid=os.getuid(),trusted_root=self.root)
        path.chmod(0o600);path.write_text('{"schema":1,"schema":1}')
        with self.assertRaises(ValueError):load(path,expected_uid=os.getuid(),trusted_root=self.root)

    def test_role_file_must_match_fixed_process_instance(self):
        with patch('online.instance_roles.load',return_value=self.company.roles),patch.dict(os.environ,
                {'SMARTPLAN_INSTANCE_ROLES_FILE':'/etc/synthetic/roles.json','SMARTPLAN_INSTANCE_ID':'f'*32}):
            with self.assertRaises(ValueError):configured()

    def test_company_dsn_scope_is_explicit_and_legacy_scope_stays_fixed(self):
        source='host=/var/run/postgresql dbname=sp_testalpha user=sp_testalpha_run'
        target='host=/var/run/postgresql dbname=sp_testalpha_restore user=sp_testalpha_run'
        validate_dsns(source,target,instance_roles=self.company.roles)
        with self.assertRaises(ValueError):validate_dsns(source,target)
        with self.assertRaises(ValueError):validate_dsns(source,target.replace('sp_testalpha_restore','sp_testbeta'),instance_roles=self.company.roles)
        with self.assertRaises(ValueError):validate_dsns(source+' password=secret',target+' password=secret',instance_roles=self.company.roles)

    def test_operator_test_guard_rejects_real_names_ports_hosts_and_credentials_options(self):
        source='host=127.0.0.1 port=55433 dbname=smartplan_check user=postgres'
        self.assertIn('dbname=sp_testalpha',p._operator_dsn(self.company,source,test_mode=True))
        for change in ('port=5432','host=example.test','dbname=real_company','user=sp_testalpha_run','options=-cfoo'):
            key=change.split('=')[0]
            altered=' '.join(v for v in source.split() if not v.startswith(key+'='))+' '+change
            with self.assertRaises(ValueError):p._operator_dsn(self.company,altered,test_mode=True)

    def test_runtime_secret_resume_keeps_keys_and_never_replaces_missing_confirmed_key(self):
        state=self.root/'state';state.mkdir(mode=0o700);privacy=state/'privacy';privacy.mkdir(mode=0o700)
        paths={'state':str(state),'privacy':str(privacy)}
        with patch.object(p.Company,'paths',return_value=paths),patch('online.instance_roles.configured',return_value=self.company.roles),patch('online.provisioning_host.pwd.getpwnam',return_value=SimpleNamespace(pw_uid=os.geteuid())):
            host._runtime_secrets(self.company)
            before=(state/'vault.key').read_bytes();checkpoint=(privacy/'key').read_bytes()
            host._runtime_secrets(self.company)
            self.assertEqual((state/'vault.key').read_bytes(),before)
            self.assertEqual((privacy/'key').read_bytes(),checkpoint)
            self.assertNotIn(before,(state/'.secret-fingerprints.json').read_bytes())
            (privacy/'key').unlink()
            with self.assertRaises(ValueError):host._runtime_secrets(self.company)
            self.assertFalse((privacy/'key').exists())

    def test_operator_binding_always_revokes_after_runtime_failure(self):
        calls=[]
        def child(company,action,**kwargs):
            calls.append(action)
            if action=='runtime-bind':raise RuntimeError('Synthetic runtime interruption')
        with patch('online.provisioning_host._child',side_effect=child),self.assertRaises(RuntimeError):host.bind_company(self.company)
        self.assertEqual(calls,['bind-grant','runtime-bind','bind-revoke'])

    def test_privileged_commands_do_not_inherit_path_or_python_selectors(self):
        with patch.dict(os.environ,{'PATH':'/untrusted','PYTHONPATH':'/untrusted'}),patch('online.provisioning_host.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=b'')) as run:
            host._run(['systemctl','show','synthetic.service'])
        environment=run.call_args.kwargs['env']
        self.assertEqual(environment['PATH'],'/usr/sbin:/usr/bin:/sbin:/bin')
        self.assertNotIn('PYTHONPATH',environment)
        self.assertEqual(host._environment(self.company)['PYTHONSAFEPATH'],'1')

    def test_listener_acceptance_proves_actual_pid_socket_ownership(self):
        def status(command,**kwargs):
            return b'active\n' if '--property=ActiveState' in command else str(os.getpid()).encode()
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as listener:
            listener.bind(('127.0.0.1',0));listener.listen(1)
            port=listener.getsockname()[1]
            with patch('online.provisioning_host._run',side_effect=status):host.verify_listener('synthetic.service',port)
        with patch('online.provisioning_host._run',side_effect=status),self.assertRaises(ValueError):host.verify_listener('synthetic.service',port)


if __name__=='__main__':unittest.main()
