"""Optional lead delivery writers obey the unchanged candidate commit boundary."""
import json
from pathlib import Path
import unittest

from test_update_flow import OperatorFlowFixture, CONFIG, APP


class LeadReplyUpdateFlowTests(OperatorFlowFixture, unittest.TestCase):
    def test_missing_optional_units_are_never_installed_enabled_or_started(self):
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in ('smartplan-lead-replies.service', 'smartplan-lead-replies.timer'):
            self.assertFalse(Path('/etc/systemd/system', name).exists())
            self.assertFalse(any(e.get('unit') == name and e.get('action') in ('start', 'enable') for e in self.events()))
        self.assert_original_data()

    def test_active_or_restarting_worker_stops_before_roles_and_clone_only_prior_timer_resumes(self):
        self.configure(lead_installed=True, lead_worker=True, lead_timer=True, lead_restarting=True)
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        events = self.events()
        stop = next(i for i, e in enumerate(events) if e.get('action') == 'stop' and e.get('unit') == 'smartplan-lead-replies.service')
        security = next(i for i, e in enumerate(events) if e.get('action') == 'security')
        clone = next(i for i, e in enumerate(events) if e.get('action') == 'prepare')
        publication = next(i for i, e in enumerate(events) if e['event'] == 'public_write')
        resume = next(i for i, e in enumerate(events) if e.get('action') == 'start' and e.get('unit') == 'smartplan-lead-replies.timer')
        self.assertLess(stop, security)
        self.assertLess(security, clone)
        self.assertLess(publication, resume)
        self.assertTrue(self.services()['smartplan-lead-replies.timer'])
        self.assertFalse(self.services()['smartplan-lead-replies.service'])
        self.assertFalse(any(e.get('action') == 'start' and e.get('unit') == 'smartplan-lead-replies.service' for e in events))
        metadata = json.loads(next((CONFIG / 'updates').glob('*/metadata.json')).read_text())
        self.assertTrue(metadata['lead_replies_present'])
        self.assertTrue(metadata['lead_timer_was_active'])
        self.assert_original_data()

    def test_inactive_prior_timer_stays_inactive_even_if_manual_worker_had_been_running(self):
        self.configure(lead_installed=True, lead_worker=True, lead_timer=False)
        result = self.run_update()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse(self.services()['smartplan-lead-replies.timer'])
        self.assertFalse(self.services()['smartplan-lead-replies.service'])
        self.assertFalse(any(e.get('unit', '').startswith('smartplan-lead-replies.') and e.get('action') == 'start' for e in self.events()))

    def test_prepublication_rollback_restores_old_release_and_prior_timer_without_replaying_oneshot(self):
        self.configure(fault='readiness', lead_installed=True, lead_worker=True, lead_timer=True)
        result = self.run_update()
        self.assertNotEqual(result.returncode, 0)
        self.assert_old_release()
        self.assertTrue(self.services()['smartplan-lead-replies.timer'])
        self.assertFalse(self.services()['smartplan-lead-replies.service'])
        self.assertFalse(any(e.get('action') == 'start' and e.get('unit') == 'smartplan-lead-replies.service' for e in self.events()))

    def test_failed_or_unconfirmed_stop_cannot_clone_or_change_configuration(self):
        for fault in ('lead_stop', 'lead_false_stop', 'lead_timer_false_stop'):
            with self.subTest(fault=fault):
                self.setUp()
                self.configure(fault=fault, lead_installed=True, lead_worker=True, lead_timer=True)
                self.assertNotEqual(self.run_update().returncode, 0)
                self.assertEqual((CONFIG / 'service.env').read_bytes(), self.original_config)
                self.assertEqual((APP / 'app/backend/generation').read_text().strip(), 'old')
                self.assertTrue(self.services()['gate'])
                self.assertTrue((CONFIG / 'UPDATE_IN_PROGRESS').exists())
                self.assertFalse(any(e.get('action') in ('security', 'prepare') for e in self.events()))
                self.assert_original_data()

    def test_unknown_effective_units_missing_half_or_active_orphan_abort_before_gate(self):
        for fault in ('lead_unit_dropin', 'lead_unit_environment', 'lead_unit_envfile',
                      'lead_unit_killmode', 'lead_unit_stop_timeout', 'missing_timer', 'orphan'):
            with self.subTest(fault=fault):
                self.setUp()
                self.configure(fault=fault, lead_installed=fault != 'orphan', lead_worker=fault == 'orphan')
                if fault == 'missing_timer':
                    Path('/etc/systemd/system/smartplan-lead-replies.timer').unlink()
                self.assertNotEqual(self.run_update().returncode, 0)
                self.assertFalse(self.services()['gate'])
                self.assertFalse(any(e['event'] == 'createdb' for e in self.events()))
                self.assertEqual((CONFIG / 'service.env').read_bytes(), self.original_config)
                self.assert_original_data()

    def test_failed_timer_resume_after_publication_never_rewinds_new_database(self):
        self.configure(fault='lead_timer_start_new', lead_installed=True, lead_timer=True)
        self.assertNotEqual(self.run_update().returncode, 0)
        self.assertEqual((APP / 'app/backend/generation').read_text().strip(), 'new')
        self.assertNotEqual((CONFIG / 'service.env').read_bytes(), self.original_config)
        self.assertTrue((CONFIG / 'UPDATE_IN_PROGRESS').exists())
        self.assertTrue(any(e['event'] == 'public_write' for e in self.events()))
        self.assert_original_data()


if __name__ == '__main__':
    unittest.main(verbosity=2)
