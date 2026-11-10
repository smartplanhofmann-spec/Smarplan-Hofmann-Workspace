"""Exact additive registry/portable export scope; no new financial horizon."""
import io
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid
import zipfile

import business_schema
import business_api
from business_company_events import TABLES,CompanyEvents
from business_assistant import Assistant
from company_export_catalog import COLUMNS,policy
from company_export_archive import build,structure,verify
from business_operations import transaction
from core import Office
import test_business_company_events as fixture

request=fixture.request


class CompanyEventRegistrationTests(unittest.TestCase):
    def test_additive_install_preserves_old_assistant_receipts_and_financial_horizon(self):
        with tempfile.TemporaryDirectory(prefix='synthetic-events-additive-') as folder:
            path=Path(folder)/'office.sqlite'
            modules=tuple(n for n in business_schema.MODULE_NAMES if n!='business_company_events')
            with patch.object(business_schema,'MODULE_NAMES',modules):
                office=Office(path)
                owner=dict(id=office.add_user('owner@example.test','Synthetic-owner-password','owner'),role='owner')
                project=office.add_project(owner,'Synthetic existing project','Synthetic customer')
                command=request(project_id=project,sources=[dict(kind='project',id=project)])
                accepted=Assistant(office).create_context(owner,command)
                old=[tuple(row) for row in office.db.execute('SELECT * FROM business_assistant_requests').fetchall()]
                horizon=business_schema.financial_accounting_horizon(office)
                office.db.close()
            upgraded=Office(path)
            try:
                self.assertEqual(Assistant(upgraded).create_context(owner,command),accepted)
                self.assertEqual([tuple(row) for row in upgraded.db.execute('SELECT * FROM business_assistant_requests').fetchall()],old)
                self.assertEqual(business_schema.financial_accounting_horizon(upgraded),horizon)
                self.assertTrue(set(TABLES)<=business_schema.registered_table_names())
                for table in TABLES:self.assertEqual(upgraded.db.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0)
                business_schema.validate_integrity(upgraded)
            finally:upgraded.db.close()

    def test_exact_export_catalog_retains_event_evidence_but_excludes_retry_working_receipts(self):
        case=fixture.CompanyEventTests();case.setUp();self.addCleanup(case.doCleanups)
        case.task();case.rule();run,_=case.scan()
        with transaction(case.office):
            inventory=structure(case.office)
            raw,manifest=build(case.office,instance_id=case.api._identity()['instance_id'],export_id=uuid.uuid4().hex,
                created_at=case.api.now(),created_by=case.owner['id'],reason='Synthetic event evidence export',inventory=inventory)
        self.assertTrue(verify(raw,instance_id=case.api._identity()['instance_id']))
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            self.assertNotIn('data/business_company_event_requests.jsonl',archive.namelist())
            rows=[json.loads(line) for line in archive.read('data/business_company_event_runs.jsonl').splitlines()]
            self.assertEqual(rows[0]['id'],run['id'])
            for table in TABLES:
                self.assertEqual([r['name'] for r in case.office.db.execute('PRAGMA table_info('+table+')')],COLUMNS[table].split(','))
                self.assertTrue(policy(table)['sensitive']);self.assertIsNone(policy(table)['retention_days'])
                self.assertEqual(policy(table)['included'],not table.endswith('_requests'))
            self.assertFalse(manifest['database_restore_supported'])
            self.assertFalse(manifest['technical_request_replay_included'])

    def test_api_is_strict_and_never_offline_and_worker_modules_are_packaged(self):
        for suffix in ('/status','/rules','/scan','/runs','/plans','/events'):
            path='/business/company-events'+suffix
            self.assertTrue(business_api.strict_workflow_path(path))
            self.assertIsNotNone(business_api.methods(path))
            self.assertFalse(business_api.offline_path(path,'GET'))
            self.assertFalse(business_api.offline_path(path,'POST'))
        root=Path(__file__).resolve().parents[1]
        spec=importlib.util.spec_from_file_location('company_event_windows_package',root/'scripts/package-windows-support.py')
        package=importlib.util.module_from_spec(spec);spec.loader.exec_module(package)
        with tempfile.TemporaryDirectory(prefix='synthetic-company-event-package-') as directory:
            archive=Path(directory)/'support.zip';package.build(archive)
            with zipfile.ZipFile(archive) as bundle:
                for module in ('business_company_events.py','company_event_sources.py','company_event_worker.py'):
                    self.assertEqual(bundle.read('Smartplan_Windows_Start_und_Sicherung/backend/'+module),(root/'backend'/module).read_bytes())


if __name__=='__main__':unittest.main()
