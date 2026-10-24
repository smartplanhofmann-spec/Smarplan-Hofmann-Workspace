"""Reject incomplete or misdirected native test packages before artifact upload."""
import base64
import importlib.util
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


release = load('native_release', 'native-release.py')
support = load('windows_support', 'package-windows-support.py')


class NativePackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='smartplan-package-check-')
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.config = self.directory / 'Generated.xcconfig'
        definitions = {'API_URL': release.API_URL, 'API_VERSION': 'v1'}
        encoded = ','.join(base64.b64encode(f'{key}={value}'.encode()).decode() for key, value in definitions.items())
        self.config.write_text('DART_DEFINES=' + encoded + '\n')

    def bundle(self, flavor):
        bundle = self.directory / 'bundle'
        bundle.mkdir()
        for name in ('smartplan_office.exe', *release.WINDOWS_DLLS):
            (bundle / name).write_bytes(b'Synthetic native-package fixture')
        (bundle / 'data/flutter_assets').mkdir(parents=True)
        if flavor == 'local':
            backend = bundle / 'backend'
            backend.mkdir()
            for name in release.BACKEND_FILES:
                shutil.copyfile(release.ROOT / 'backend' / name, backend / name)
            for name in ('Starten.cmd', 'Sicherung_erstellen.cmd', 'Sicherung_wiederherstellen.cmd', 'Run.cmd', 'START_HIER.txt'):
                (bundle / name).write_text('Synthetic launcher')
            self.config.write_text('# local default, no remote definitions\n')
        return bundle

    def ios_info(self):
        path = self.directory / 'Info.plist'
        info = {'CFBundleIdentifier': release.BUNDLE_ID, 'CFBundleVersion': '109',
                'CFBundleShortVersionString': release.version()[0], 'UIDeviceFamily': [1, 2],
                'NSFaceIDUsageDescription': 'Synthetic unlock description',
                'UISupportedInterfaceOrientations~ipad': ['UIInterfaceOrientationPortrait']}
        path.write_bytes(plistlib.dumps(info))
        return path, info

    def test_current_sources_include_phone_tablet_and_keychain_configuration(self):
        checked = release.source_checks()
        self.assertEqual(checked['supported_devices'], ['iPhone', 'iPad', 'Windows x64'])
        self.assertEqual(checked['visible_app_version'], release.version()[0])
        # The visible Semver is independent of TestFlight's increasing build counter.
        app = self.directory / 'app'
        (app / 'lib').mkdir(parents=True)
        (app / 'pubspec.yaml').write_text('version: 0.11.0+915\n')
        (app / 'lib/app_version.dart').write_text("const smartplanVersion = '0.8.0';\n")
        with self.assertRaisesRegex(ValueError, 'Sichtbare Appversion'):
            release.source_checks(self.directory)

    def test_local_package_rejects_omitted_plan_backend_and_accepts_complete_sources(self):
        bundle = self.bundle('local')
        release.check_windows(bundle, self.config, 'local')
        for name in ('plan_deletions.py', 'project_workspace.py', 'inquiries.py',
                     'inbound_connectors.py', 'inquiry_attachments.py', 'workspace_api.py'):
            with self.subTest(omitted=name):
                (bundle / 'backend' / name).unlink()
                with self.assertRaisesRegex(ValueError, name):
                    release.check_windows(bundle, self.config, 'local')
                shutil.copyfile(release.ROOT / 'backend' / name, bundle / 'backend' / name)

    def test_online_package_rejects_missing_native_storage_library_and_local_startup(self):
        bundle = self.bundle('online')
        release.check_windows(bundle, self.config, 'online')
        for name in ('flutter_secure_storage_windows_plugin.dll', 'url_launcher_windows_plugin.dll',
                     'share_plus_plugin.dll', 'pdfium.dll', 'pdfrx_pdfium_gate.dll'):
            with self.subTest(omitted=name):
                (bundle / name).unlink()
                with self.assertRaisesRegex(ValueError, name):
                    release.check_windows(bundle, self.config, 'online')
                (bundle / name).write_bytes(b'Synthetic fixture')
        (bundle / 'Starten.cmd').write_text('Must not ship')
        with self.assertRaisesRegex(ValueError, 'Backend-Starter'):
            release.check_windows(bundle, self.config, 'online')

    def test_release_checks_reject_a_build_targeting_the_other_backend(self):
        with self.assertRaisesRegex(ValueError, 'entfernte API'):
            release.check_api(self.config, 'local')
        self.config.write_text('# Missing online configuration\n')
        with self.assertRaisesRegex(ValueError, 'Online-Ziel'):
            release.check_api(self.config, 'online')

    def test_ios_requires_ipad_and_expected_signed_keychain_identity(self):
        info_path, info = self.ios_info()
        release.check_ios(info_path, self.config, '109')
        info['UIDeviceFamily'] = [1]
        info_path.write_bytes(plistlib.dumps(info))
        with self.assertRaisesRegex(ValueError, 'iPhone und iPad'):
            release.check_ios(info_path, self.config, '109')
        info['UIDeviceFamily'] = [1, 2]
        info_path.write_bytes(plistlib.dumps(info))
        entitlements = self.directory / 'signed.plist'
        entitlements.write_bytes(plistlib.dumps({'com.apple.developer.team-identifier': 'TESTTEAM00',
            'application-identifier': 'TESTTEAM00.' + release.BUNDLE_ID, 'keychain-access-groups': []}))
        release.check_ios(info_path, self.config, '109', signed_entitlements=entitlements, team='TESTTEAM00')
        with self.assertRaisesRegex(ValueError, 'Apple-Team'):
            release.check_ios(info_path, self.config, '109', signed_entitlements=entitlements, team='OTHERTEAM0')

    def test_manifest_identifies_commit_backend_and_every_packaged_file(self):
        bundle = self.bundle('online')
        release.write_windows_manifest(bundle, release.manifest('online', 'a' * 40))
        saved = json.loads((bundle / 'RELEASE_MANIFEST.json').read_text())
        self.assertEqual(saved['source_commit'], 'a' * 40)
        self.assertEqual(saved['version'], release.version()[0])
        self.assertEqual(saved['visible_app_version'], release.version()[0])
        self.assertEqual(saved['build_number'], release.version()[1])
        self.assertEqual(saved['required_backend_schema'], 6)
        self.assertEqual(saved['required_backend_capabilities'],
                         ['project_workspace', 'inquiry_intake', 'gmail_intake', 'offline_workspace', 'plan_deletion',
                          'mail_attachments', 'business_integrations'])
        self.assertNotIn('draft_backend_capabilities', saved)
        self.assertEqual(saved['offline_modules'], ['project_plans', 'plan_import_sources', 'project_workspace'])
        self.assertIs(saved['test_package'], True)
        self.assertIn('flutter_secure_storage_windows_plugin.dll', saved['files_sha256'])
        self.assertIn('url_launcher_windows_plugin.dll', saved['files_sha256'])
        self.assertIn('share_plus_plugin.dll', saved['files_sha256'])
        self.assertIn('pdfium.dll', saved['files_sha256'])
        self.assertIn('pdfrx_pdfium_gate.dll', saved['files_sha256'])
        self.assertNotIn('RELEASE_MANIFEST.json', saved['files_sha256'])

    def test_local_manifest_keeps_packaged_backend_and_project_plan_scope(self):
        saved = release.manifest('local', 'b' * 40)
        self.assertEqual(saved['api_url'], 'http://127.0.0.1:8765')
        self.assertEqual(saved['api_version'], '')
        self.assertIsNone(saved['required_backend_schema'])
        self.assertEqual(saved['required_backend_capabilities'], [])
        self.assertNotIn('draft_backend_capabilities', saved)
        self.assertEqual(saved['offline_modules'], ['project_plans'])
        self.assertIs(saved['test_package'], True)

    def test_ios_cli_manifest_requires_workspace_backend_and_actual_build_number(self):
        info_path, _ = self.ios_info()
        output = self.directory / 'ios-manifest.json'
        subprocess.run([sys.executable, str(release.ROOT / 'scripts/native-release.py'), 'ios',
                        '--plist', str(info_path), '--config', str(self.config),
                        '--build-number', '109', '--commit', 'c' * 40, '--output', str(output)],
                       check=True, timeout=15, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        saved = json.loads(output.read_text())
        self.assertEqual(saved['source_commit'], 'c' * 40)
        self.assertEqual(saved['version'], release.version()[0])
        self.assertEqual(saved['visible_app_version'], release.version()[0])
        self.assertEqual(saved['build_number'], '109')
        self.assertEqual(saved['required_backend_schema'], 6)
        self.assertEqual(saved['required_backend_capabilities'],
                         ['project_workspace', 'inquiry_intake', 'gmail_intake', 'offline_workspace', 'plan_deletion',
                          'mail_attachments', 'business_integrations'])
        self.assertNotIn('draft_backend_capabilities', saved)
        self.assertEqual(saved['supported_devices'], ['iPhone', 'iPad'])
        self.assertIs(saved['signed_entitlements_checked'], False)
        self.assertIs(saved['test_package'], True)

    def test_actual_support_archive_imports_the_packaged_backend(self):
        archive = self.directory / 'support.zip'
        support.build(archive)
        with zipfile.ZipFile(archive) as stream:
            expected = {'Smartplan_Windows_Start_und_Sicherung/backend/' + name for name in support.BACKEND_FILES}
            expected.update('Smartplan_Windows_Start_und_Sicherung/' + name for name in support.WINDOWS_FILES)
            self.assertEqual(set(stream.namelist()), expected, 'Package must contain only the explicit source/launcher whitelist')
            stream.extractall(self.directory / 'unpacked')
        python = release.ROOT / 'backend/.venv' / ('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
        self.assertTrue(python.exists(), 'Backend virtualenv is required for the real package import check')
        subprocess.run([str(python), '-E', '-c', 'import server, plan_access, plans, plan_deletions\n'
                        'import project_workspace, inquiries, inbound_connectors, workspace_api\n'
                        'import inquiry_attachments, external_integrations, integration_bridge\n'
                        'from core import Office\n'
                        'office = Office("synthetic-package.db")\n'
                        'office.db.close()'],
                       cwd=self.directory / 'unpacked/Smartplan_Windows_Start_und_Sicherung/backend',
                       check=True, timeout=15, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


if __name__ == '__main__':
    unittest.main(verbosity=2)
