"""Exercise real plist/CLI boundaries; actual distribution signing remains macOS CI."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import plistlib
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).with_name('ios-archive-entitlements.py')
SPEC = importlib.util.spec_from_file_location('ios_archive_entitlements', SCRIPT)
archive = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(archive)


class ArchiveEntitlements(unittest.TestCase):
    def setUp(self):
        self.team = 'TESTTEAM00'
        self.prefix = 'OLDAPPID00'  # App ID prefix is not necessarily the team ID.
        self.app_id = self.prefix + '.' + archive.BUNDLE_ID
        self.now = datetime(2026, 11, 10, tzinfo=timezone.utc)
        self.source = {'keychain-access-groups': [archive.SOURCE_GROUP]}
        self.signed = {'application-identifier': self.app_id,
            'com.apple.developer.team-identifier': self.team, 'get-task-allow': False,
            'beta-reports-active': True}
        self.profile = {'TeamIdentifier': [self.team], 'ApplicationIdentifierPrefix': [self.prefix],
            'ExpirationDate': self.now + timedelta(days=365),
            'Entitlements': {**self.signed, 'keychain-access-groups': [self.prefix + '.*']}}

    def resolve(self, source=None, signed=None, profile=None):
        return archive.resolve(self.source if source is None else source,
            self.signed if signed is None else signed,
            self.profile if profile is None else profile, self.team, now=self.now)

    def test_actual_app_prefix_is_preserved_without_guessing_team_prefix(self):
        originals = deepcopy((self.source, self.signed, self.profile))
        resolved = self.resolve()
        self.assertEqual(resolved, {**self.signed, 'keychain-access-groups': [self.app_id]})
        self.assertEqual((self.source, self.signed, self.profile), originals)
        self.assertNotEqual(self.prefix, self.team)
        self.assertEqual(self.resolve(signed=resolved), resolved)
        profile = deepcopy(self.profile)
        profile['Entitlements']['keychain-access-groups'] = [self.app_id]
        self.assertEqual(self.resolve(profile=profile), resolved)

    def test_refuses_invented_capabilities_and_unresolved_or_shared_source_groups(self):
        for source in ({}, {'keychain-access-groups': []},
                       {'keychain-access-groups': [self.app_id]},
                       {**self.source, 'aps-environment': 'production'}):
            with self.subTest(source=source), self.assertRaises(ValueError):
                self.resolve(source=source)
        for change in ({'application-identifier': self.team + '.' + archive.BUNDLE_ID},
                       {'application-identifier': self.prefix + '.other-app'},
                       {'com.apple.developer.team-identifier': self.prefix},
                       {'get-task-allow': True}, {'get-task-allow': 0},
                       {'keychain-access-groups': [self.prefix + '.*']},
                       {'keychain-access-groups': [self.app_id, self.prefix + '.other-app']},
                       {'aps-environment': 'production'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.resolve(signed={**self.signed, **change})

    def test_requires_actual_current_app_store_profile_and_matching_grant(self):
        changes = [{'TeamIdentifier': [self.prefix]}, {'ApplicationIdentifierPrefix': [self.team]},
            {'Entitlements': {}}, {'ExpirationDate': self.now}, {'ExpirationDate': '2099'},
            {'ProvisionedDevices': ['synthetic-device']}, {'ProvisionsAllDevices': True}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.resolve(profile={**self.profile, **change})
        for change in ({'application-identifier': self.prefix + '.other-app'},
                       {'com.apple.developer.team-identifier': self.prefix},
                       {'get-task-allow': True}, {'keychain-access-groups': []},
                       {'keychain-access-groups': [self.team + '.*']}):
            profile = deepcopy(self.profile)
            profile['Entitlements'].update(change)
            with self.subTest(entitlement=change), self.assertRaises(ValueError):
                self.resolve(profile=profile)
        naive = deepcopy(self.profile)
        naive['ExpirationDate'] = naive['ExpirationDate'].replace(tzinfo=None)
        self.assertEqual(self.resolve(profile=naive), self.resolve())

    def test_real_cli_writes_validated_plist_and_refuses_overwrite_or_invalid_grant(self):
        with tempfile.TemporaryDirectory(prefix='smartplan-ios-entitlements-') as directory:
            directory = Path(directory)
            args = [sys.executable, str(SCRIPT), '--team', self.team]
            for flag, value in (('source', self.source), ('signed-entitlements', self.signed),
                                ('provisioning-profile', self.profile)):
                path = directory / (flag + '.plist')
                # plist dates have no timezone; real security cms uses the same format.
                value = deepcopy(value)
                if flag == 'provisioning-profile':
                    value['ExpirationDate'] = datetime(2099, 1, 1)
                path.write_bytes(plistlib.dumps(value))
                args.extend(['--' + flag, str(path)])
            output = directory / 'resolved.plist'
            args.extend(['--output', str(output)])
            result = subprocess.run(args, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIs(json.loads(result.stdout)['ready_for_final_export'], False)
            contents = output.read_bytes()
            self.assertEqual(plistlib.loads(contents), self.resolve())
            duplicate = subprocess.run(args, capture_output=True, text=True, timeout=10)
            self.assertEqual(duplicate.returncode, 2)
            self.assertEqual(output.read_bytes(), contents)
            output.unlink()
            profile_path = directory / 'provisioning-profile.plist'
            profile_path.write_bytes(plistlib.dumps({}))
            denied = subprocess.run(args, capture_output=True, text=True, timeout=10)
            self.assertEqual(denied.returncode, 2)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
