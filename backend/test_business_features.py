"""Feature support is additive metadata, never a permission or a device grant."""
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

import business_api
from core import Office


class BusinessFeatureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.office = Office(Path(temporary.name) / 'synthetic.db')
        self.addCleanup(self.office.db.close)
        self.owner = {'id': self.office.add_user('owner@example.test', 'Synthetic-password-123', 'owner'), 'role': 'owner'}
        self.tech = {'id': self.office.add_user('tech@example.test', 'Synthetic-password-123', 'technician'), 'role': 'technician'}

    def module(self, name, features):
        return types.SimpleNamespace(__name__=name, FEATURES=features, dispatch=lambda *args: None)

    def test_only_installed_modules_advertise_features_without_granting_finance(self):
        foundation = self.module('business_foundation', ('billing_contact',))
        absent = self.module('business_not_installed', ('must_stay_hidden',))
        with patch.object(business_api, '_modules', return_value=[foundation, absent]):
            meta = business_api.capabilities(self.office, self.tech)
        self.assertEqual(meta['features'], ['billing_contact'])
        self.assertNotIn('finance.read', meta['permissions'])
        self.assertNotIn('business_not_installed', meta['capabilities'])

    def test_old_packaged_modules_without_features_remain_supported(self):
        module = types.SimpleNamespace(__name__='business_foundation', dispatch=lambda *args: None)
        with patch.object(business_api, '_modules', return_value=[module]):
            meta = business_api.capabilities(self.office, self.owner)
        self.assertEqual(meta['features'], [])
        self.assertEqual(meta['capabilities'], ['business_foundation'])

    def test_offline_device_metadata_never_inherits_billing_features(self):
        foundation = self.module('business_foundation', ('billing_contact',))
        with patch.object(business_api, '_modules', return_value=[foundation]):
            meta, status, _ = business_api.dispatch(self.office, self.owner,
                '/business/capabilities', 'GET', {}, offline=True, offline_capabilities=['field_media'])
        self.assertEqual(status, 200)
        self.assertEqual(meta['features'], [])
        self.assertEqual(meta['capabilities'], [])
        self.assertNotIn('finance.read', meta['permissions'])


if __name__ == '__main__':
    unittest.main()
