"""Actual MFA, restricted PostgreSQL runtime and original backup/restore sources."""
import tempfile
import unittest
from urllib.parse import urlencode

import psycopg
from psycopg.conninfo import make_conninfo
import business_schema
from business_sales import protected_tables
from communication_history import CommunicationHistory
from online import release, test_business_sales_pg as sales
from online.backup import backup
from online.restore import restore, complete_restore
from online.store import PostgresOffice

fixture = sales.fixture
req = sales.req


@unittest.skipUnless(fixture.DSN, 'Guarded disposable PostgreSQL fixture required')
class CommunicationHistoryPostgres(unittest.TestCase):
    setUp = sales.SalesPostgres.setUp
    reopen = sales.SalesPostgres.reopen
    login = sales.SalesPostgres.login
    call = sales.SalesPostgres.call
    command = sales.SalesPostgres.command
    adopt_body = sales.SalesPostgres.adopt_body
    workflow = sales.SalesPostgres.workflow

    def seed(self):
        data = self.workflow()
        self.pid = data['project']['project_id']
        self.scope = dict(customer_id=self.contact['id'], project_id=self.pid)
        self.path = '/business/sales/communication-history?' + urlencode(self.scope)
        self.call('POST', '/business/feed', req(project_id=self.pid, text='Synthetic PG project communication'), status=201)
        case = self.call('POST', '/business/service/cases', req(revision=0,
            customer_id=self.contact['id'],project_id=self.pid,person_id=None,asset_id=None,
            contract_id=None,visit_id=None,inquiry_id=None,defect_id=None,title='Synthetic PG service communication',
            kind='request',priority='normal',responsible_id=self.owner['id'],follow_up_on=None,
            description='Synthetic service source')).json
        return self.call('GET', self.path).json

    def test_actual_mfa_source_projection_restart_fresh_grants_and_device_denial(self):
        before=self.seed()
        self.assertEqual({i['kind'] for i in before['items']},{'inquiry','sales','service','document','project_note'})
        self.assertEqual(self.office.db.execute('SELECT current_user').fetchone()[0],'smartplan-online')
        self.assertTrue(business_schema.require_runtime_security(self.office))
        self.reopen();self.assertEqual(self.call('GET',self.path).json,before)
        technician=self.call('POST','/users',dict(email='history-tech@example.test',password='Synthetic-history-tech-password-123',role='technician'),status=201).json
        token=self.login('history-tech@example.test','Synthetic-history-tech-password-123')
        self.call('GET',self.path,token=token,status=404)
        self.office.assign(self.owner,self.pid,technician['id'])
        self.call('POST','/business/settings/permissions',req(user_id=technician['id'],permission='contacts.read',scope='*',effect='allow',revision=0))
        visible=self.call('GET',self.path,token=token).json
        self.assertFalse({'inquiry','document','delivery'}&{i['kind'] for i in visible['items']})
        self.call('POST','/business/settings/permissions',req(user_id=technician['id'],permission='contacts.read',scope=self.pid,effect='deny',revision=0))
        self.call('GET',self.path,token=token,status=403)
        device=self.call('POST','/business/offline/access',{},status=201).json['token']
        self.call('GET',self.path,token=device,status=403)
        self.call('GET',self.path,{'ignored':True},status=400)
        self.call('GET',self.path+'&ignored=1',status=400)
        business_schema.validate_integrity(self.office)

    def test_actual_backup_restore_preserves_canonical_snapshot_without_new_message_store(self):
        expected=self.seed();actor=self.owner
        source=release.snapshot_fingerprint(fixture.DSN)
        self.office.db.close()
        target=make_conninfo(fixture.DSN,dbname='smartplan_release_check')
        release.validate_dsns(fixture.DSN,target,test_mode=True)
        with psycopg.connect(fixture.DSN,autocommit=True) as admin:
            if admin.execute("SELECT 1 FROM pg_database WHERE datname='smartplan_release_check'").fetchone():
                raise RuntimeError('Existing restore target must remain untouched')
            admin.execute('CREATE DATABASE smartplan_release_check OWNER "smartplan-migrator" TEMPLATE template0')
        try:
            with tempfile.TemporaryDirectory(prefix='communication-history-pg-restore-') as directory:
                saved=backup(fixture.DSN,directory)
                self.assertTrue(restore(saved,fixture.DSN,target,privileged_operator=True,test_mode=True)['restore_pending'])
            runtime=make_conninfo(self.runtime,dbname='smartplan_release_check')
            verifier=PostgresOffice(runtime,allow_restore_pending=True)
            try:self.assertFalse(complete_restore(verifier)['restore_pending'])
            finally:verifier.db.close()
            recovered=PostgresOffice(runtime)
            try:
                self.assertEqual(CommunicationHistory(recovered).listing(actor,self.scope),expected)
                business_schema.validate_integrity(recovered)
                restored=release.snapshot_fingerprint(target)
                for table in protected_tables():self.assertEqual(restored[table],source[table])
                self.assertEqual(release.snapshot_fingerprint(fixture.DSN),source)
            finally:recovered.db.close()
        finally:
            with psycopg.connect(fixture.DSN,autocommit=True) as admin:admin.execute('DROP DATABASE smartplan_release_check')


if __name__=='__main__':unittest.main()
