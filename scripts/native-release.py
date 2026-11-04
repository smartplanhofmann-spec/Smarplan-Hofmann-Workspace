"""Validate native test packages and record exactly which source/config they contain."""
import argparse
import ast
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import plistlib
import re

ROOT = Path(__file__).resolve().parent.parent
API_URL = 'https://office.smartplan-hofmann.de'
BUNDLE_ID = 'de.smartplanhofmann.office'
BACKEND_FILES = ('backup.py', 'restore.py', 'core.py', 'server.py', 'onedrive.py',
                 'windows_office.py', 'plans.py', 'plan_access.py', 'plan_deletions.py',
                 'project_workspace.py', 'inquiries.py', 'inbound_connectors.py', 'inquiry_attachments.py',
                 'workspace_api.py', 'external_integrations.py', 'integration_bridge.py',
                 'business_api.py', 'business_schema.py', 'business_foundation.py',
                 'business_documents.py', 'business_pricing.py', 'business_finance.py', 'business_einvoice.py', 'business_delivery.py',
                 'business_planning.py', 'business_time.py', 'business_operations.py', 'business_offline_reports.py', 'business_project_economics.py', 'business_asset_provenance.py', 'business_customer_workspace.py', 'business_personnel_workflow.py', 'business_accounting_euer.py', 'business_accounting_openings.py', 'business_assistant.py', 'business_assistant_sources.py', 'business_assistant_provider.py', 'business_assistant_speech.py', 'business_payroll.py', 'business_payroll_statements.py', 'payroll_travel_2026_v1.py', 'payroll_travel_recording.py', 'payroll_travel_mixed_2026.py', 'payroll_travel_link.py', 'payroll_travel_ground_2026.py', 'payroll_travel_2026_v3.py', 'payroll_sickness_2026.py', 'payroll_sickness_phases_2026.py', 'payroll_sickness_start_2026.py', 'payroll_wage_interruptions_2026.py', 'business_payroll_wage_interruptions.py', 'payroll_pap_oneoff_2026.py', 'payroll_oneoff_2026.py', 'payroll_oneoff_composition_2026.py', 'payroll_oneoff_runs.py', 'payroll_entitlement_dispatch.py', 'payroll_annual_basis_2026.py', 'business_payroll_calculation_cases.py', 'business_payroll_annual_basis.py', 'business_payroll_oneoff_cases.py', 'payroll_calculations_2026.py', 'payroll_claims_composition_2026.py', 'payroll_segments_2026.py', 'payroll_travel_tax_2026.py', 'payroll_travel_2026_v2.py', 'payroll_travel_expenses_2026.py', 'travel_payroll_sources.py', 'payroll_de_2026.py', 'payroll_transition_2026.py', 'business_payroll_facts.py', 'payroll_holidays_2026.py', 'payroll_entitlements_2026.py', 'business_payroll_entitlements.py', 'payroll_periods_2026.py', 'payroll_pap_periods_2026.py', 'accounting_invoice_sources.py', 'business_overview.py', 'business_migrations.py', 'business_custom_fields.py', 'business_privacy_cases.py', 'privacy_case_sources.py', 'business_payroll_cash.py', 'payroll_cash_sources.py', 'accounting_travel_sources.py', 'travel_allowance_cash.py', 'business_travel_allowances.py', 'payroll_travel_2026.py', 'payroll_travel_transport_2026.py', 'payroll_travel_rates_2026.py', 'business_service.py', 'business_bank_reconciliation.py', 'business_resource_custody.py', 'business_purchase_changes.py', 'company_export_archive.py', 'company_export_verify.py', 'company_export_catalog.py', 'business_company_handover.py', 'business_payroll_accounts.py', 'payroll_ledger.py', 'business_sales.py', 'payroll_pap_2026.py', 'business_inventory_counts.py',
                 'business_inventory.py', 'business_maintenance.py', 'business_adapters.py', 'business_catalog_imports.py',
                 'business_organization.py', 'business_instance.py', 'business_purchasing.py', 'business_portal.py', 'business_accounting.py',
                 'business_accounting_allocations.py', 'business_accounting_components.py', 'business_accounting_refunds.py', 'business_accounting_capacity.py', 'accounting_component_segments.py', 'business_accounting_refunds_v2.py', 'accounting_joint_ledger.py', 'accounting_joint_access.py', 'accounting_joint_order.py', 'accounting_return_lots.py', 'business_accounting_profile.py',
                 'requirements.lock')
WINDOWS_DLLS = ('flutter_windows.dll', 'printing_plugin.dll', 'pdfium.dll', 'file_selector_windows_plugin.dll',
                'flutter_secure_storage_windows_plugin.dll', 'local_auth_windows_plugin.dll',
                'url_launcher_windows_plugin.dll', 'share_plus_plugin.dll', 'record_windows_plugin.dll', 'pdfrx_pdfium_gate.dll',
                'msvcp140.dll', 'vcruntime140.dll', 'vcruntime140_1.dll')
OFFLINE_INSTALLER_FILES = ('Python_Umgebung_aktualisieren.cmd', 'Python_Umgebung_aktualisieren.py')
OPERATOR_FILES = ('scripts/reconcile-accounting-restore.py', 'docs/CRM_ERP_EUER_BETRIEB.md', 'docs/CRM_ERP_ANFANGSSALDEN_API.md', 'docs/CRM_ERP_ANFANGSSALDEN_CLIENTS.md', 'docs/CRM_ERP_KATALOG_BROWSER_2026-11-04.md', 'docs/evidence/accounting-openings-domain-2026-11-04.json', 'docs/evidence/accounting-openings-postgres-first-2026-11-04.json',
                  'docs/CRM_ERP_EUER_E1A_API.md', 'docs/CRM_ERP_EUER_E1B1_API.md', 'docs/CRM_ERP_EUER_E1B2_API.md', 'docs/CRM_ERP_EUER_E1B3A_API.md', 'docs/CRM_ERP_EUER_E1B3B_API.md', 'docs/CRM_ERP_EUER_E1B3C_API.md', 'docs/CRM_ERP_EUER_E1B4A1_API.md', 'docs/CRM_ERP_OFFLINE_SERVICEBERICHTE.md', 'docs/CRM_ERP_ENTSCHEIDUNGEN.md', 'docs/CRM_ERP_EUER_WORKFLOW_API.md', 'docs/CRM_ERP_EUER_CLIENTS.md', 'docs/CRM_ERP_EUER_REGELQUELLEN_2026.md', 'docs/CRM_ERP_PERSONAL_WORKFLOW.md', 'docs/CRM_ERP_LOHN_QUELLEN.md', 'docs/CRM_ERP_UNTERNEHMENSEXPORT.md', 'docs/CRM_ERP_LOHN_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_LOHN_CLIENTS.md', 'docs/CRM_ERP_LOHN_MIDIJOB_2026.md', 'docs/CRM_ERP_LOHN_MIDIJOB_CLIENTS.md', 'docs/CRM_ERP_LOHN_ZEITACHSEN_API.md', 'docs/CRM_ERP_LOHN_ANSPRUECHE_GEGENPRUEFUNG_2026.md', 'docs/CRM_ERP_LOHN_ANSPRUECHE_2026.md', 'docs/CRM_ERP_LOHN_ANSPRUECHE_API.md', 'docs/CRM_ERP_LOHN_GESAMTFALL_KERNEL_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_REISE_V3_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_REISE_V3_VERTRAG_2026.md', 'docs/evidence/payroll-travel-policy-clients-2026-11-03.json', 'docs/CRM_ERP_REISE_PAUSCHALSTEUER_CLIENTS.md', 'docs/CRM_ERP_LOHN_ANSPRUECHE_CLIENTS_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_LOHN_ANSPRUECHE_CLIENTS.md', 'docs/CRM_ERP_LOHN_KRANKHEIT_VERSIONEN_2026.md', 'docs/CRM_ERP_LOHN_GESAMTFALL_CLIENTS.md', 'docs/CRM_ERP_LOHN_GESAMTFALL_CLIENTS_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_LOHN_U_MERKMAL_VERTRAG_2026.md', 'docs/CRM_ERP_LOHN_U_MERKMAL_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_LOHN_U_MERKMAL_CLIENTS.md', 'docs/CRM_ERP_LOHN_U_MERKMAL_NATIVE_PRUEFUNG_2026-11-03.md', 'docs/CRM_ERP_LOHN_JAHRESQUELLEN_NATIVE_GEGENPRUEFUNG_2026-11-03.md', 'docs/CRM_ERP_LOHN_NULLMONAT_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_LOHN_EINMALBEZUG_V6_VERTRAG_2026.md', 'docs/CRM_ERP_LOHN_EINMALBEZUG_PG_PRUEFUNG_2026-11-04.md', 'docs/CRM_ERP_LOHN_EINMALBEZUG_CLIENTS.md', 'docs/payroll-oneoff-own-statements-2026-11-04.md', 'docs/CRM_ERP_LOHN_NULLNETTO_BROWSERPRUEFUNG_2026-11-04.md', 'docs/evidence/payroll-oneoff-clients-2026-11-04.json', 'docs/evidence/payroll-oneoff-pg-annual-integration-2026-11-04.json', 'docs/evidence/payroll-oneoff-pg-annual-final-2026-11-04.json', 'docs/CRM_ERP_LOHN_JAHRESBASIS_VERTRAG_2026.md', 'docs/CRM_ERP_LOHN_JAHRESBASIS_GEGENPRUEFUNG_2026.md', 'docs/CRM_ERP_LOHN_JAHRESQUELLEN_CLIENTS.md', 'docs/CRM_ERP_LOHN_JAHRESQUELLEN_CLIENTS_PRUEFUNG_2026-11-03.json', 'docs/evidence/payroll-travel-core-regression-2026-11-03.json', 'docs/CRM_ERP_LOHN_BERECHNUNGSFAELLE_API.md', 'docs/CRM_ERP_LOHN_GESAMTFALL_GEGENPRUEFUNG_2026.md', 'docs/CRM_ERP_REISE_PAUSCHALSTEUER_GEGENPRUEFUNG_2026.md', 'docs/evidence/travel-clients-2026-11-03.json', 'docs/CRM_ERP_REISEPAUSCHALEN_CLIENTS.md', 'docs/CRM_ERP_REISE_PAUSCHALSTEUER_2026.md', 'docs/CRM_ERP_LOHN_MITARBEITERBELEG_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_LOHN_MITARBEITERBELEG_API.md', 'docs/CRM_ERP_LOHN_MITARBEITERBELEG.md', 'docs/CRM_ERP_LOHN_ZEITACHSEN_CLIENTS_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_LOHN_ZEITACHSEN_CLIENTS.md', 'docs/CRM_ERP_LOHN_FAKTEN_2026.md', 'docs/CRM_ERP_LOHN_FAKTEN_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_LOHN_TEILMONATE_2026.md', 'docs/CRM_ERP_LOHN_TEILMONATE_PRUEFUNG_2026-11-03.json', 'docs/evidence/travel-rates-2026-transcription.json', 'docs/CRM_ERP_REISEPAUSCHALEN_API.md', 'docs/CRM_ERP_LOHN_MIDIJOB_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_LOHN_RECHENWERK_2026.md', 'docs/CRM_ERP_ASSISTENT.md', 'docs/CRM_ERP_SPRACHE.md', 'docs/CRM_ERP_DATEIMIGRATION.md', 'docs/CRM_ERP_DATEIIMPORT.md', 'docs/CRM_ERP_ZUSATZFELDER.md', 'docs/CRM_ERP_KONFORMITAET_QUELLEN.md', 'docs/CRM_ERP_ABHAENGIGKEITEN_SICHERHEIT.md', 'docs/evidence/product-source-bom.json', 'docs/evidence/source-advisories-2026-11-03.json', 'docs/CRM_ERP_VERTRIEB.md', 'docs/CRM_ERP_SERVICE.md', 'docs/CRM_ERP_SERVICE_CLIENTS.md', 'docs/CRM_ERP_DATENSCHUTZFAELLE.md', 'docs/CRM_ERP_LOHNZAHLUNGEN_EUER_CLIENTS.md', 'docs/CRM_ERP_BANKABGLEICH_API.md', 'docs/CRM_ERP_BANKABGLEICH.md', 'docs/CRM_ERP_BANKABGLEICH_CLIENTS.md', 'docs/CRM_ERP_BANKABGLEICH_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_BANK_EUER_INTEGRATION_PRUEFUNG.md', 'docs/CRM_ERP_BEDIENBARKEIT.md', 'docs/CRM_ERP_BENUTZERHANDBUCH.md', 'docs/CRM_ERP_BETRIEBSMITTEL.md', 'docs/CRM_ERP_BETRIEBSMITTEL_CLIENTS.md', 'docs/CRM_ERP_EINKAUF_RETOUREN.md', 'docs/CRM_ERP_EINKAUF_RETOUREN_API.md', 'docs/CRM_ERP_EINKAUF_RETOUREN_CLIENTS.md', 'docs/CRM_ERP_PROVISIONIERUNG.md', 'docs/CRM_ERP_PROVISIONIERUNG_SICHERHEITSPRUEFUNG.md', 'docs/evidence/accessibility-2026-11-03.json', 'docs/CRM_ERP_LOHNZAHLUNGEN_EUER.md', 'docs/CRM_ERP_LOHNZAHLUNGEN_EUER_API.md', 'docs/CRM_ERP_EUER_KETTEN_ANALYSE.md', 'docs/CRM_ERP_INVENTUR.md', 'docs/CRM_ERP_UNTERNEHMENSUEBERSICHT.md', 'docs/CRM_ERP_ASSISTENT_CLIENTS.md', 'docs/CRM_ERP_KUNDENARBEITSBEREICH.md', 'docs/CRM_ERP_GERAETEHERKUNFT.md', 'docs/CRM_ERP_PROJEKTWIRTSCHAFTLICHKEIT_CLIENTS.md')


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
    visible = re.search(r'''^\s*const(?:\s+String)?\s+smartplanVersion\s*=\s*['"](\d+\.\d+\.\d+)['"]\s*;''',
                        (root / 'app/lib/app_version.dart').read_text(), re.MULTILINE)
    require(visible and visible.group(1) == release,
            'Sichtbare Appversion muss mit der Semver aus pubspec.yaml übereinstimmen.')
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
    for name in OPERATOR_FILES:
        require((root / name).is_file(), f'Betreiber-Paketquelle fehlt: {name}')
    return {'version': release, 'visible_app_version': visible.group(1), 'default_build_number': build,
            'supported_devices': ['iPhone', 'iPad', 'Windows x64']}


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


def offline_installer(root=ROOT):
    spec = importlib.util.spec_from_file_location('smartplan_offline_installer', root / 'windows' / OFFLINE_INSTALLER_FILES[1])
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    return installer


def write_wheel_manifest(directory, root=ROOT):
    installer = offline_installer(root)
    manifest = installer.wheel_manifest(directory, root / 'backend/requirements.lock')
    (Path(directory) / installer.MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return manifest


def local_backend(bundle, root=ROOT):
    directory = Path(bundle) / 'backend'
    for name in OPERATOR_FILES:
        packaged = Path(bundle) / name
        require(packaged.is_file() and packaged.read_bytes() == (root / name).read_bytes(),
                f'Betreiberdatei fehlt oder stimmt nicht mit der Quelle überein: {name}')
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
        for name in OFFLINE_INSTALLER_FILES:
            require((bundle / name).is_file() and (bundle / name).read_bytes() == (root / 'windows' / name).read_bytes(),
                    f'Offline-Updater fehlt oder stimmt nicht mit der Quelle ueberein: {name}')
        offline_installer(root).verify_wheel_manifest(bundle / 'python-wheels', bundle / 'backend/requirements.lock')
    else:
        require(not (bundle / 'backend').exists() and not list(bundle.glob('*.cmd'))
                and not (bundle / 'python-wheels').exists()
                and not any((bundle / name).exists() for name in OFFLINE_INSTALLER_FILES),
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
    require(bool(info.get('NSMicrophoneUsageDescription')), 'Mikrofonbeschreibung fehlt im gebauten Paket.')
    require('audio' not in info.get('UIBackgroundModes', []), 'Hintergrundaufnahme ist für Sprachentwürfe nicht vorgesehen.')
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
    return {'schema_version': 1, 'version': version(root)[0], 'visible_app_version': version(root)[0],
            'build_number': version(root)[1],
            'source_commit': commit, 'api_url': API_URL if kind == 'online' else 'http://127.0.0.1:8765',
            'api_version': 'v1' if kind == 'online' else '', 'required_backend_schema': 7 if kind == 'online' else None,
            'required_backend_capabilities': ['project_workspace', 'inquiry_intake', 'gmail_intake',
                                              'offline_workspace', 'plan_deletion', 'mail_attachments',
                                              'business_integrations', 'business_suite'] if kind == 'online' else [],
            'offline_modules': ['project_plans', 'plan_import_sources', 'project_workspace',
                                'time_events', 'field_media']
                               if kind == 'online' else ['project_plans'],
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
    wheels = sub.add_parser('wheels', help='Validate complete CPython3.12/Windows-x64 locked wheels and record checksums')
    wheels.add_argument('--directory', required=True, type=Path)
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
    elif args.action == 'wheels':
        checked = write_wheel_manifest(args.directory)
        print('Windows-x64/Python-3.12 Offline-Wheels geprueft: ' + str(len(checked['versions'])))
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
