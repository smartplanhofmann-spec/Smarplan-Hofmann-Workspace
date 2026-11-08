"""Prospective parser checks must precede downtime and database preparation."""
import json
from pathlib import Path
import shutil
import unittest

from test_update_flow import OperatorFlowFixture, APP, CONFIG, IMPORT_RUNTIME, NEW, STATE


class ParserPreflightUpdateTests(OperatorFlowFixture, unittest.TestCase):
    def assert_before_maintenance_failure(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assert_old_release()
        self.assertFalse((CONFIG / 'UPDATE_IN_PROGRESS').exists())
        self.assertFalse(any((CONFIG / 'updates').glob('*/metadata.json')))
        self.assertEqual(len(list((STATE / 'databases').glob('*.json'))), 1)
        forbidden = {'security', 'prepare', 'maintenance'}
        self.assertFalse(any(event.get('action') in forbidden or event['event'] in
                             ('createdb', 'public_write') for event in self.events()))
        self.assertFalse(any(event.get('action') in ('stop', 'restart', 'reload')
                             for event in self.events()))

    def test_probe_uses_prospective_code_with_real_service_uid_and_no_database_credentials(self):
        self.configure(import_worker=True)
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        proof = json.loads((STATE / 'doctor/evidence.json').read_text())
        self.assertEqual((proof['uid'], proof['gid'], proof['no_new_privileges']), (2001, 2001, 1))
        self.assertEqual(proof['prospective_generation'], 'new')
        self.assertEqual(proof['installed_generation'], 'old')
        self.assertIn('/releases/' + NEW[:12] + '-', proof['cwd'])
        self.assertTrue(proof['api_was_running'])
        self.assertFalse(proof['gate_was_active'])
        self.assertFalse(proof['pending_update_exists'])
        self.assertIn('--doctor', proof['arguments'])
        self.assertEqual(proof['arguments'][proof['arguments'].index('--worker-python') + 1],
                         str(IMPORT_RUNTIME / 'venv/bin/python'))
        for key in ('SMARTPLAN_DATABASE_DSN', 'SMARTPLAN_VAULT_KEY_FILE', 'PYTHONPATH', 'HOME', 'HTTP_PROXY'):
            self.assertNotIn(key, proof['environment_names'])
        self.assertTrue(self.services()['smartplan-plan-import.service'])

    def test_incompatible_or_unconfirmed_parser_never_stops_services_or_prepares_a_database(self):
        for fault in ('preflight_doctor', 'preflight_false_ready', 'preflight_no_sandbox',
                      'preflight_wrong_languages', 'preflight_missing_namespace',
                      'preflight_unbounded_tmp', 'preflight_bad_json'):
            with self.subTest(fault=fault):
                self.setUp()
                self.configure(fault=fault, import_worker=True)
                self.assert_before_maintenance_failure(self.run_update())
                self.assertTrue(self.services()['smartplan-plan-import.service'])

    def test_installed_but_inactive_parser_is_checked_and_remains_inactive_on_failure(self):
        self.configure(fault='preflight_doctor', import_worker=False)
        self.assert_before_maintenance_failure(self.run_update())
        self.assertFalse(self.services()['smartplan-plan-import.service'])

    def test_missing_installed_parser_runtime_is_rejected_before_maintenance(self):
        self.configure(import_worker=True)
        shutil.rmtree(IMPORT_RUNTIME)
        self.assert_before_maintenance_failure(self.run_update())
        self.assertTrue(self.services()['smartplan-plan-import.service'])

    def test_installation_without_optional_parser_does_not_require_or_create_one(self):
        self.configure(worker_installed=False)
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((STATE / 'doctor/evidence.json').exists())
        self.assertFalse(IMPORT_RUNTIME.exists())
        self.assertEqual((APP / 'SOURCE_COMMIT').read_text().strip(), NEW)


if __name__ == '__main__':
    unittest.main()
