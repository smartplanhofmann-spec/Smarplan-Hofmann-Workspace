"""Validate native test packages and record exactly which source/config they contain."""
import argparse
import ast
import base64
import hashlib
import json
from pathlib import Path
import plistlib
import re

ROOT = Path(__file__).resolve().parent.parent
API_URL = 'https://office.smartplan-hofmann.de'
BUNDLE_ID = 'de.smartplanhofmann.office'
BACKEND_FILES = ('backup.py', 'restore.py', 'core.py', 'server.py', 'onedrive.py',
                 'windows_office.py', 'plans.py', 'plan_access.py', 'requirements.lock')
WINDOWS_DLLS = ('flutter_windows.dll', 'printing_plugin.dll', 'file_selector_windows_plugin.dll',
                'flutter_secure_storage_windows_plugin.dll', 'local_auth_windows_plugin.dll',
                'msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def version(root=ROOT):
    match = re.search(r'^version:\s*(\d+\.\d+\.\d+)\+(\d+)\s*$',
                      (root / 'app/pubspec.yaml').read_text(), re.MULTILINE)
    require(match, 'pubspec.yaml braucht Version und numerische Buildnummer.')
    return match.group(1), match.group(2)


def source_checks(root=ROOT):
    release, build = version(root)
    with (root / 'app/ios/Runner/Info.plist').open('rb') as stream:
        info = plistlib.load(stream)
    require(bool(info.get('NSFaceIDUsageDescription')), 'Face-ID-Beschreibung fehlt.')
    require(bool(info.get('NSCameraUsageDescription')), 'Kamera-Beschreibung fehlt.')
    with (root / 'app/ios/Runner/Runner.entitlements').open('rb') as stream:
        entitlements = plistlib.load(stream)
    require(isinstance(entitlements.get('keychain-access-groups'), list), 'Keychain-Entitlement fehlt.')
    project = (root / 'app/ios/Runner.xcodeproj/project.pbxproj').read_text()
    require(project.count('CODE_SIGN_ENTITLEMENTS = Runner/Runner.entitlements;') == 3,
            'Keychain-Entitlements müssen für Debug/Profile/Release eingerichtet sein.')
    require(project.count('TARGETED_DEVICE_FAMILY = "1,2";') == 3,
            'iPhone und iPad müssen in allen App-Konfigurationen enthalten sein.')
    for name in BACKEND_FILES:
        require((root / 'backend' / name).is_file(), f'Backend-Paketquelle fehlt: {name}')
    return {'version': release, 'default_build_number': build, 'supported_devices': ['iPhone', 'iPad', 'Windows x64']}


def definitions(config):
    # Generated.xcconfig and Windows generated_config.cmake both contain this value.
    match = re.search(r'(?:^|["\n])DART_DEFINES=([^"\r\n]*)', Path(config).read_text())
    encoded = match.group(1) if match else ''
    return dict(base64.b64decode(item, validate=True).decode().split('=', 1)
                for item in encoded.split(',') if item)


def check_api(config, flavor):
    values = definitions(config)
    if flavor == 'online':
        require(values.get('API_URL') == API_URL and values.get('API_VERSION') == 'v1',
                'Online-Ziel oder API-Version im erzeugten Build fehlt.')
    else:
        require('API_URL' not in values and 'API_VERSION' not in values,
                'Lokales Paket darf keine entfernte API-Konfiguration enthalten.')


def local_backend(bundle, root=ROOT):
    directory = Path(bundle) / 'backend'
    for name in BACKEND_FILES:
        source, packaged = root / 'backend' / name, directory / name
        require(packaged.is_file() and packaged.read_bytes() == source.read_bytes(),
                f'Backend-Datei fehlt oder stimmt nicht mit der Quelle überein: {name}')
    # Includes imports inside methods, such as the plan validator in Office.save_plan.
    local_modules = {path.stem for path in (root / 'backend').glob('*.py')}
    packaged_modules = {Path(name).stem for name in BACKEND_FILES if name.endswith('.py')}
    for name in BACKEND_FILES:
        if not name.endswith('.py'):
            continue
        for node in ast.walk(ast.parse((directory / name).read_text(encoding='utf-8'))):
            imports = ([alias.name.split('.')[0] for alias in node.names] if isinstance(node, ast.Import)
                       else [node.module.split('.')[0]] if isinstance(node, ast.ImportFrom) and node.module else [])
            for module in imports:
                require(module not in local_modules or module in packaged_modules,
                        f'Lokales Backend benötigt eine nicht gepackte Datei: {module}.py')


def check_windows(bundle, config, flavor, root=ROOT):
    bundle = Path(bundle)
    check_api(config, flavor)
    for name in ('smartplan_office.exe', *WINDOWS_DLLS):
        require((bundle / name).is_file() and (bundle / name).stat().st_size > 0,
                f'Windows-Paketdatei fehlt: {name}')
    require((bundle / 'data/flutter_assets').is_dir(), 'Flutter-Assets fehlen.')
    if flavor == 'local':
        local_backend(bundle, root)
        for name in ('Starten.cmd', 'Sicherung_erstellen.cmd', 'Sicherung_wiederherstellen.cmd', 'Run.cmd', 'START_HIER.txt'):
            require((bundle / name).is_file(), f'Lokaler Starter fehlt: {name}')
    else:
        require(not (bundle / 'backend').exists() and not list(bundle.glob('*.cmd')),
                'Online-Paket enthält einen lokalen Backend-Starter.')
    return {'platform': 'windows-x64', 'flavor': flavor}


def check_ios(info_path, config, build, root=ROOT, signed_entitlements=None, team=None):
    check_api(config, 'online')
    with Path(info_path).open('rb') as stream:
        info = plistlib.load(stream)
    require(info.get('CFBundleIdentifier') == BUNDLE_ID, 'Falsche iOS-Bundle-ID.')
    require(str(info.get('CFBundleVersion')) == str(build), 'Falsche iOS-Buildnummer.')
    require(info.get('CFBundleShortVersionString') == version(root)[0], 'Falsche iOS-Appversion.')
    require(set(info.get('UIDeviceFamily', [])) == {1, 2}, 'Gebautes Paket unterstützt nicht iPhone und iPad.')
    require(bool(info.get('NSFaceIDUsageDescription')), 'Face-ID-Beschreibung fehlt im gebauten Paket.')
    require(bool(info.get('UISupportedInterfaceOrientations~ipad')), 'iPad-Ausrichtungen fehlen im gebauten Paket.')
    if signed_entitlements:
        with Path(signed_entitlements).open('rb') as stream:
            entitlements = plistlib.load(stream)
        require(team and entitlements.get('com.apple.developer.team-identifier') == team,
                'Signiertes Paket hat nicht das erwartete Apple-Team.')
        require(entitlements.get('application-identifier', '').endswith('.' + BUNDLE_ID),
                'Signierte App-Kennung stimmt nicht überein.')
        require(isinstance(entitlements.get('keychain-access-groups'), list), 'Signiertes Keychain-Entitlement fehlt.')
        require(entitlements.get('get-task-allow') is not True, 'TestFlight-Paket enthält Debugger-Freigabe.')
    return {'platform': 'ios', 'flavor': 'online', 'build_number': str(build),
            'supported_devices': ['iPhone', 'iPad'], 'signed_entitlements_checked': bool(signed_entitlements)}


def manifest(kind, commit, root=ROOT):
    require(re.fullmatch(r'[a-f0-9]{40}', commit), 'Vollständiger Quell-Commit fehlt.')
    return {'schema_version': 1, 'version': version(root)[0], 'build_number': version(root)[1],
            'source_commit': commit, 'api_url': API_URL if kind == 'online' else 'http://127.0.0.1:8765',
            'api_version': 'v1' if kind == 'online' else '', 'required_backend_schema': 3 if kind == 'online' else None,
            'offline_modules': ['project_plans', 'plan_import_sources'] if kind == 'online' else ['project_plans'],
            'offline_max_days': 7, 'test_package': True}


def write_windows_manifest(bundle, data):
    bundle = Path(bundle)
    filename = 'RELEASE_MANIFEST.json'
    data['files_sha256'] = {}
    for path in sorted(bundle.rglob('*')):
        require(not path.is_symlink(), 'Paket darf keine symbolischen Dateiverweise enthalten.')
        if path.is_file() and path.name != filename:
            with path.open('rb') as stream:
                data['files_sha256'][path.relative_to(bundle).as_posix()] = hashlib.file_digest(stream, 'sha256').hexdigest()
    (bundle / filename).write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('source')
    windows = sub.add_parser('windows')
    windows.add_argument('--bundle', type=Path, required=True)
    windows.add_argument('--config', type=Path, required=True)
    windows.add_argument('--flavor', choices=['local', 'online'], required=True)
    windows.add_argument('--commit', required=True)
    ios = sub.add_parser('ios')
    ios.add_argument('--plist', type=Path, required=True)
    ios.add_argument('--config', type=Path, required=True)
    ios.add_argument('--build-number', required=True)
    ios.add_argument('--commit', required=True)
    ios.add_argument('--output', type=Path, required=True)
    ios.add_argument('--signed-entitlements', type=Path)
    ios.add_argument('--team')
    args = parser.parse_args()
    source_checks()
    if args.action == 'source':
        print(json.dumps(source_checks(), ensure_ascii=False))
    elif args.action == 'windows':
        checked = check_windows(args.bundle, args.config, args.flavor)
        write_windows_manifest(args.bundle, {**manifest(args.flavor, args.commit), **checked})
        print('Windows-Paket und Quell-/Dateimanifest geprüft.')
    else:
        checked = check_ios(args.plist, args.config, args.build_number,
                            signed_entitlements=args.signed_entitlements, team=args.team)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps({**manifest('online', args.commit), **checked}, indent=2) + '\n', encoding='utf-8')
        print('iPhone-/iPad-Paket und Buildmanifest geprüft.')


if __name__ == '__main__':
    main()
