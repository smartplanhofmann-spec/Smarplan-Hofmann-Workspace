"""Actual runtime-role MFA and full restore keep release metadata outside company data."""
import json
from pathlib import Path
import unittest
import time
from online.auth import totp
from unittest.mock import patch

import business_schema
from online import installation
from online import test_business_company_handover_pg as bound
from online import test_business_journey_pg as fixture
from online.store import PostgresOffice
from online.web import create_app
from online.storage import Storage
from online.test_postgres_accounting_components_integration import disposable_restore,evidence_for,approve


@unittest.skipUnless(fixture.DSN,'Guarded own disposable PostgreSQL required')
class InstallationPostgres(unittest.TestCase):
    setUp=bound.CompanyHandoverPostgres.setUp
    reopen=bound.CompanyHandoverPostgres.reopen
    call=bound.CompanyHandoverPostgres.call
    def login(self,email,password):
        pending=self.call('POST','/login',dict(email=email,password=password),token=None).json
        self.assertTrue(pending['mfa_required'])
        if 'enrollment' in pending:self._mfa_secret=pending['enrollment']['secret']
        deadline=time.monotonic()+31
        while getattr(self,'_last_mfa_step',None)==int(time.time()//30):
            if time.monotonic()>deadline:raise AssertionError('A fresh real MFA step was not reached')
            time.sleep(0.2)
        step=int(time.time()//30)
        result=self.call('POST','/login/verify',dict(challenge=pending['challenge'],code=totp(self._mfa_secret,step)),token=None).json
        self._last_mfa_step=step
        return result['token']

    def test_actual_mfa_read_is_nonwriting_and_restore_does_not_restore_an_old_code_marker(self):
        marker=Path(self.directory.name)/'BUILD_SOURCE.json'
        installation.write_context(marker,'c'*40)
        with patch.object(installation,'MARKER',marker):self.reopen()
        tables=[row[0] for row in self.office.db.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' AND tablename LIKE ?",('business_%',))]
        def counts(office):return {name:office.db.execute('SELECT COUNT(*) FROM '+name).fetchone()[0] for name in tables}
        before=counts(self.office)
        original=self.call('GET','/business/installation').json
        self.assertEqual(original,dict(schema_version=1,status='recorded',source_commit='c'*40,api_compatibility_version='0.12.0-online-pilot'))
        self.assertEqual(before,counts(self.office))
        self.assertIn('installation_context',self.call('GET','/business/capabilities').json['features'])
        self.assertTrue(business_schema.validate_integrity(self.office))
        self.office.db.close()
        with disposable_restore(self.runtime)as(target,runtime,report):
            operator=PostgresOffice(target)
            try:approve(operator,evidence_for(operator,report))
            finally:operator.db.close()
            restored=PostgresOffice(runtime)
            try:
                newer=Path(self.directory.name)/'NEW_BUILD_SOURCE.json'
                installation.write_context(newer,'d'*40)
                with patch.object(installation,'MARKER',newer):
                    app=create_app(office=restored,key=self.key,host='office.example.test',instance_id=self.instance,
                        storage=Storage(restored,self.key,'office.example.test',config=self.storage_config))
                client=app.test_client()
                result=client.get('/api/v1/business/installation',base_url='https://office.example.test',headers={'Authorization':'Bearer '+self.token})
                self.assertEqual(result.status_code,401,result.data[:200])
                self.client=client
                self.token=self.login('order-owner@example.test','Synthetic-owner-password-123')
                result=self.call('GET','/business/installation')
                self.assertEqual(result.json['source_commit'],'d'*40)
                self.assertEqual(json.loads(marker.read_text())['source_commit'],'c'*40)
                self.assertTrue(business_schema.validate_integrity(restored))
            finally:restored.db.close()


if __name__=='__main__':unittest.main()
