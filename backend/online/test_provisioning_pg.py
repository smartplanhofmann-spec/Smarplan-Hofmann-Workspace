"""Two real company databases/roles/processes in the reserved disposable cluster.

No host accounts or production services are created. Both API processes use the
fixture UID; independent OS UID isolation is a separate container acceptance.
"""
from dataclasses import replace
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request
import uuid

from cryptography.fernet import Fernet
import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo,conninfo_to_dict

import business_schema
from core import Problem
from online import provisioning as p
from online.instance import bind,verify,InstanceConfigurationError
from online.storage import Storage
from online.store import PostgresOffice,migrate
from online.auth import totp
from online.backup import backup
from online.restore import restore,restore_dump,complete_restore
from online.test_provisioning import company

DSN=os.environ.get('SMARTPLAN_TEST_DSN')


def serve_fixture(company_value,dsn,key,directory,privacy,ports):
    from werkzeug.serving import make_server,WSGIRequestHandler
    from online.web import create_app
    item=p.parse(company_value);os.environ.update(privacy)
    office=PostgresOffice(dsn,instance_roles=item.roles)
    storage=Storage(office,key,item.public_host,config={'server':{'path':directory}})
    app=create_app(office=office,key=key,host=item.public_host,storage=storage,instance_id=item.instance_id)
    class Quiet(WSGIRequestHandler):
        def log(self,*args,**kwargs):pass
    server=make_server('127.0.0.1',0,app,request_handler=Quiet)
    ports.put(server.server_port)
    server.serve_forever()


@unittest.skipUnless(DSN,'Reserved disposable PostgreSQL 55433 required')
class ProvisioningPostgres(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='synthetic-two-company-');self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.companies=[];self.databases=[];self.roles=[];self.processes=[]
        self.addCleanup(self.cleanup)
        for index in range(2):
            item=company('test'+uuid.uuid4().hex[:12],instance_id=uuid.uuid4().hex,
                privacy_installation_id=uuid.uuid4().hex,port=18910+index)
            p._operator_dsn(item,DSN,test_mode=True)
            self.roles.extend([item.roles.runtime,item.roles.owner]);self.databases.append(item.roles.database)
            password='Synthetic-company-runtime-'+uuid.uuid4().hex
            p.prepare_database(item,DSN,test_mode=True,runtime_password=password)
            runtime=make_conninfo(DSN,dbname=item.roles.database,user=item.roles.runtime,password=password)
            directory=self.root/item.slug;directory.mkdir(mode=0o700)
            key=Fernet.generate_key()
            def binder():
                office=PostgresOffice(runtime,instance_roles=item.roles)
                try:bind(office,item.instance_id,item.public_host,key,Storage(office,key,item.public_host,config={'server':{'path':str(directory/'documents')}}))
                finally:office.db.close()
            p.initial_bind(item,DSN,binder,test_mode=True)
            privacy={'SMARTPLAN_PRIVACY_CHECKPOINT_FILE':str(directory/'checkpoint.json'),
                'SMARTPLAN_PRIVACY_CHECKPOINT_KEY_FILE':str(directory/'checkpoint.key'),
                'SMARTPLAN_PRIVACY_INSTALLATION_ID':item.privacy_installation_id}
            Path(privacy['SMARTPLAN_PRIVACY_CHECKPOINT_KEY_FILE']).write_bytes(os.urandom(32))
            Path(privacy['SMARTPLAN_PRIVACY_CHECKPOINT_KEY_FILE']).chmod(0o600)
            office=PostgresOffice(runtime,instance_roles=item.roles)
            try:
                office.add_user('same-owner@example.test','Synthetic-owner-password-123','owner')
                with patch.dict(os.environ,privacy):business_schema.initialize_privacy_checkpoint(office)
            finally:office.db.close()
            self.companies.append(dict(company=item,dsn=runtime,key=key,directory=directory,privacy=privacy,binder=binder))

    def cleanup(self):
        for process in self.processes:
            if process.is_alive():process.terminate()
            process.join(timeout=5)
        with psycopg.connect(DSN,autocommit=True) as admin:
            for name in reversed(self.databases):
                # Names come only from this test's new random manifests.
                admin.execute(sql.SQL('DROP DATABASE IF EXISTS {}').format(sql.Identifier(name)))
            for name in reversed(self.roles):
                admin.execute(sql.SQL('DROP ROLE IF EXISTS {}').format(sql.Identifier(name)))

    def office(self,item):return PostgresOffice(item['dsn'],instance_roles=item['company'].roles)

    def test_two_real_http_processes_mfa_objects_storage_and_current_role_drift(self):
        context=multiprocessing.get_context('spawn')
        for item in self.companies:
            ports=context.Queue();process=context.Process(target=serve_fixture,args=(item['company'].document(),item['dsn'],item['key'],str(item['directory']/'documents'),item['privacy'],ports));process.start();self.processes.append(process)
            item['port']=ports.get(timeout=15)
            challenge=self.call(item,'/login',{'email':'same-owner@example.test','password':'Synthetic-owner-password-123'})
            item['token']=self.call(item,'/login/verify',{'challenge':challenge['challenge'],'code':totp(challenge['enrollment']['secret'],int(time.time()//30))})['token']
            item['project']=self.call(item,'/projects',{'name':item['company'].slug,'customer':item['company'].slug},status=201)['id']
        first,second=self.companies
        for own,other in ((first,second),(second,first)):
            self.call(own,'/projects',token=other['token'],status=401)
            projects=self.call(own,'/projects');self.assertEqual([row['id'] for row in projects],[own['project']])
            self.call(own,'/projects/'+other['project']+'/reports',status=404)
            with self.assertRaises(psycopg.Error):
                psycopg.connect(make_conninfo(own['dsn'],dbname=other['company'].roles.database))
            office=self.office(own)
            try:
                self.assertTrue(business_schema.require_runtime_security(office))
                storage=Storage(office,own['key'],own['company'].public_host,config={'server':{'path':str(own['directory']/'documents')}})
                verify(office,own['company'].instance_id,own['company'].public_host,own['key'],storage)
                storage.backends['server'].put('a'*32,'b'*32,('%PDF-1.4\n'+own['company'].slug+'\n%%EOF').encode())
            finally:office.db.close()
        self.assertNotEqual((first['directory']/'documents'/('a'*32)/('b'*32+'.pdf')).read_bytes(),(second['directory']/'documents'/('a'*32)/('b'*32+'.pdf')).read_bytes())
        a,b=first['company'].roles,second['company'].roles
        with psycopg.connect(DSN,autocommit=True) as admin:
            for foreign_role in (b.owner,b.runtime):
                admin.execute(sql.SQL('GRANT {} TO {}').format(sql.Identifier(foreign_role),sql.Identifier(a.runtime)))
                office=self.office(first)
                try:
                    with self.assertRaises(Problem):business_schema.require_runtime_security(office)
                finally:office.db.close()
                admin.execute(sql.SQL('REVOKE {} FROM {}').format(sql.Identifier(foreign_role),sql.Identifier(a.runtime)))
            admin.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(b.database),sql.Identifier(a.runtime)))
            for item in self.companies:
                office=self.office(item)
                try:
                    with self.assertRaises(Problem):business_schema.require_runtime_security(office)
                finally:office.db.close()
            admin.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM {}').format(sql.Identifier(b.database),sql.Identifier(a.runtime)))
            # This negative legacy-scope check must also run in a fresh
            # disposable cluster, without earlier release suites creating it.
            if not admin.execute("SELECT 1 FROM pg_roles WHERE rolname='smartplan-migrator'").fetchone():
                admin.execute('CREATE ROLE "smartplan-migrator" NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS')
                self.roles.append('smartplan-migrator')
            legacy='legacy_company_test_'+uuid.uuid4().hex[:12];self.databases.append(legacy)
            admin.execute(sql.SQL('CREATE DATABASE {} OWNER "smartplan-migrator"').format(sql.Identifier(legacy)))
            admin.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(legacy)))
            admin.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(legacy),sql.Identifier(a.runtime)))
            office=self.office(first)
            try:
                with self.assertRaises(Problem):business_schema.require_runtime_security(office)
            finally:
                office.db.close()
                admin.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM {}').format(sql.Identifier(legacy),sql.Identifier(a.runtime)))

    def call(self,item,path,body=None,*,token=None,status=200):
        token=token or item.get('token')
        headers={'Host':item['company'].public_host,'X-Forwarded-Proto':'https','Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        request=urllib.request.Request('http://127.0.0.1:'+str(item['port'])+'/api/v1'+path,
            data=json.dumps(body).encode() if body is not None else None,headers=headers)
        try:response=urllib.request.urlopen(request,timeout=10)
        except urllib.error.HTTPError as error:response=error
        self.assertEqual(response.status,status,path)
        value=response.read()
        return json.loads(value) if value else None

    def test_repeat_preparation_and_initial_bind_cleanup_never_migrate_running_company(self):
        item=self.companies[0];company_=item['company'];roles=company_.roles
        foreign=make_conninfo(DSN,dbname=self.companies[1]['company'].roles.database)
        with self.assertRaises(ValueError):migrate(foreign,owner_role=roles.owner,instance_roles=roles)
        p.prepare_database(company_,DSN,test_mode=True)
        def fail():raise RuntimeError('Synthetic interruption')
        with self.assertRaises(RuntimeError):p.initial_bind(company_,DSN,fail,test_mode=True)
        office=self.office(item)
        try:
            self.assertFalse(office.db.execute("SELECT has_any_column_privilege(current_user,'business_instance_identity','INSERT')").fetchone()[0])
            with patch('online.store.migrate') as migration:
                with self.assertRaises(RuntimeError):p.prepare_database(company_,DSN,test_mode=True)
                migration.assert_not_called()
            # Model a grant left by process death before the finally block.
            with psycopg.connect(DSN,autocommit=True) as admin:
                target=make_conninfo(DSN,dbname=roles.database)
                with psycopg.connect(target,autocommit=True) as db:
                    db.execute(sql.SQL('GRANT INSERT ON business_instance_identity TO {}').format(sql.Identifier(roles.runtime)))
            with self.assertRaises(ValueError):p.initial_bind(company_,DSN,fail,test_mode=True)
            self.assertFalse(office.db.execute("SELECT has_any_column_privilege(current_user,'business_instance_identity','INSERT')").fetchone()[0])
        finally:office.db.close()
        fresh=company('test'+uuid.uuid4().hex[:12],instance_id=uuid.uuid4().hex,privacy_installation_id=uuid.uuid4().hex)
        self.roles.extend([fresh.roles.runtime,fresh.roles.owner]);self.databases.append(fresh.roles.database)
        password='Synthetic-first-bind-'+uuid.uuid4().hex
        p.prepare_database(fresh,DSN,test_mode=True,runtime_password=password)
        runtime=make_conninfo(DSN,dbname=fresh.roles.database,user=fresh.roles.runtime,password=password)
        def initial_failure():
            first=PostgresOffice(runtime,instance_roles=fresh.roles)
            try:
                self.assertTrue(first.db.execute("SELECT has_any_column_privilege(current_user,'business_instance_identity','INSERT')").fetchone()[0])
                raise RuntimeError('Synthetic failure after actual initial INSERT grant')
            finally:first.db.close()
        with self.assertRaises(RuntimeError):p.initial_bind(fresh,DSN,initial_failure,test_mode=True)
        first=PostgresOffice(runtime,instance_roles=fresh.roles)
        try:
            self.assertEqual(first.db.execute('SELECT COUNT(*) FROM business_instance_identity').fetchone()[0],0)
            self.assertFalse(first.db.execute("SELECT has_any_column_privilege(current_user,'business_instance_identity','INSERT')").fetchone()[0])
        finally:first.db.close()

    def target(self,item,label):
        name=item['company'].roles.database+'_'+label;self.databases.append(name)
        with psycopg.connect(DSN,autocommit=True) as admin:
            admin.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(name),sql.Identifier(item['company'].roles.owner)))
            admin.execute(sql.SQL('REVOKE ALL ON DATABASE {} FROM PUBLIC').format(sql.Identifier(name)))
        return make_conninfo(item['dsn'],dbname=name)

    def test_actual_backup_restore_binding_foreign_dump_and_missing_checkpoint_fail_closed(self):
        first,second=self.companies;roles=first['company'].roles
        saved=backup(first['dsn'],first['directory']/'backups')
        target=self.target(first,'restore')
        source_admin=make_conninfo(DSN,dbname=roles.database)
        target_admin=make_conninfo(DSN,dbname=conninfo_to_dict(target)['dbname'])
        restore(saved,source_admin,target_admin,privileged_operator=True,test_mode=True,instance_roles=roles)
        restored=PostgresOffice(target,allow_restore_pending=True,instance_roles=roles)
        try:
            with patch.dict(os.environ,{},clear=True),self.assertRaises(Exception):
                with restored.lock,restored.db:complete_restore(restored)
            self.assertEqual(restored.db.execute('SELECT pending FROM business_restore_state').fetchone()[0],1)
            with patch.dict(os.environ,second['privacy']),self.assertRaises(Exception):
                with restored.lock,restored.db:complete_restore(restored)
            with patch.dict(os.environ,first['privacy']):
                with restored.lock,restored.db:complete_restore(restored)
            self.assertEqual(restored.db.execute('SELECT pending FROM business_restore_state').fetchone()[0],0)
            self.assertEqual(restored.db.execute('SELECT financial_reconciliation_required FROM business_restore_state').fetchone()[0],1)
        finally:restored.db.close()
        foreign=backup(second['dsn'],second['directory']/'backups');wrong=self.target(first,'foreign')
        target_admin=make_conninfo(DSN,dbname=conninfo_to_dict(wrong)['dbname'])
        # Restore an intentionally foreign archive into an isolated empty target.
        restore_dump(foreign,source_admin,target_admin,owner_role=roles.owner,instance_roles=roles)
        with self.assertRaises(ValueError):PostgresOffice(target_admin,allow_restore_pending=True,instance_roles=roles)
        with self.assertRaises(ValueError):migrate(target_admin,owner_role=roles.owner,instance_roles=roles)
        other=self.office(second)
        try:self.assertEqual(other.db.execute('SELECT instance_id FROM business_instance_identity').fetchone()[0],second['company'].instance_id)
        finally:other.db.close()


if __name__=='__main__':unittest.main()
