"""Actual CLI entrypoint with temporary DBs and existing instance-worker gate."""
from contextlib import redirect_stderr,redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import uuid

from core import Office
import test_business_company_events as fixture


class CompanyEventWorkerCLI(unittest.TestCase):
    setUp=fixture.CompanyEventTests.setUp
    task=fixture.CompanyEventTests.task
    rule=fixture.CompanyEventTests.rule

    def command(self,*,instance,host):
        path=Path(__file__).resolve().parents[1]/'scripts/process-company-events.py'
        spec=importlib.util.spec_from_file_location('company_event_worker_cli_under_test',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        argv=[str(path),'--actor-id',self.owner['id'],'--request-id',uuid.uuid4().hex]
        output=io.StringIO();errors=io.StringIO()
        # Substitute only the database constructor: the CLI, actual Office,
        # binding check and domain action are real. No PostgreSQL contact.
        with patch('online.store.PostgresOffice',side_effect=lambda dsn:Office(self.path)),patch('sys.argv',argv),patch.dict(os.environ,{
            'SMARTPLAN_DATABASE_DSN':'synthetic-constructor-only',
            'SMARTPLAN_INSTANCE_ID':instance,'SMARTPLAN_PUBLIC_HOST':host}),redirect_stdout(output),redirect_stderr(errors):
            status=module.main()
        return status,output.getvalue(),errors.getvalue()

    def test_cli_rejects_wrong_fixed_company_before_scan_or_actual_task(self):
        self.task();self.rule()
        status,output,error=self.command(instance=uuid.uuid4().hex,host='events.example.test')
        self.assertEqual(status,1);self.assertEqual(output,'')
        self.assertNotIn('synthetic-constructor-only',error)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0],1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_company_event_runs').fetchone()[0],0)

    def test_cli_rejects_wrong_host_and_accepts_exact_bound_company(self):
        self.task();self.rule()
        identity=self.office.db.execute('SELECT instance_id FROM business_instance_identity').fetchone()[0]
        self.assertEqual(self.command(instance=identity,host='other.example.test')[0],1)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0],1)
        self.assertEqual(self.command(instance=identity,host='events.example.test')[0],0)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM workspace_items').fetchone()[0],2)
        self.assertEqual(self.office.db.execute('SELECT COUNT(*) FROM business_company_event_executions').fetchone()[0],1)


if __name__=='__main__':unittest.main()
