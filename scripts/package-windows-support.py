"""Build reproducible Windows support sources for the development package."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import zipfile

ROOT = Path(__file__).resolve().parent.parent
BACKEND_FILES = ("backup.py", "restore.py", "core.py", "server.py", "onedrive.py",
                 "windows_office.py", "plans.py", "plan_access.py", "plan_deletions.py",
                 "project_workspace.py", "inquiries.py", "inbound_connectors.py", "inquiry_attachments.py",
                 "workspace_api.py", "external_integrations.py", "integration_bridge.py",
                 "business_api.py", "business_schema.py", "business_foundation.py",
                 "business_documents.py", "business_pricing.py", "business_finance.py", "business_einvoice.py", "business_delivery.py",
                 "business_planning.py", "business_time.py", "business_operations.py", "business_offline_reports.py", "business_project_economics.py", "business_asset_provenance.py", "business_customer_workspace.py", "business_personnel_workflow.py", "business_accounting_euer.py", "business_assistant.py", "business_assistant_sources.py", "business_assistant_provider.py", "business_assistant_speech.py", "business_payroll.py", "business_payroll_statements.py", "payroll_travel_2026_v1.py", "payroll_travel_recording.py", "payroll_travel_mixed_2026.py", "payroll_travel_link.py", "payroll_travel_ground_2026.py", "payroll_travel_2026_v3.py", "payroll_sickness_2026.py", "payroll_sickness_phases_2026.py", "payroll_sickness_start_2026.py", "payroll_wage_interruptions_2026.py", "payroll_pap_oneoff_2026.py", "payroll_oneoff_2026.py", "payroll_entitlement_dispatch.py", "payroll_annual_basis_2026.py", "business_payroll_calculation_cases.py", "business_payroll_annual_basis.py", "payroll_calculations_2026.py", "payroll_claims_composition_2026.py", "payroll_segments_2026.py", "payroll_travel_tax_2026.py", "payroll_travel_2026_v2.py", "payroll_travel_expenses_2026.py", "travel_payroll_sources.py", "payroll_de_2026.py", "payroll_transition_2026.py", "business_payroll_facts.py", "payroll_holidays_2026.py", "payroll_entitlements_2026.py", "business_payroll_entitlements.py", "payroll_periods_2026.py", "payroll_pap_periods_2026.py", "accounting_invoice_sources.py", "business_inventory_counts.py", "payroll_pap_2026.py", "business_overview.py", "business_migrations.py", "business_custom_fields.py", "business_privacy_cases.py", "privacy_case_sources.py", "business_payroll_cash.py", "payroll_cash_sources.py", "accounting_travel_sources.py", "travel_allowance_cash.py", "business_travel_allowances.py", "payroll_travel_2026.py", "payroll_travel_transport_2026.py", "payroll_travel_rates_2026.py", "business_service.py", "business_bank_reconciliation.py", "business_resource_custody.py", "business_purchase_changes.py", "company_export_archive.py", "company_export_verify.py", "company_export_catalog.py", "business_company_handover.py", "business_payroll_accounts.py", "payroll_ledger.py", "business_sales.py",
                 "business_inventory.py", "business_maintenance.py", "business_adapters.py",
                 "business_organization.py", "business_instance.py", "business_purchasing.py", "business_portal.py", "business_accounting.py",
                 "business_accounting_allocations.py", "business_accounting_components.py", "business_accounting_refunds.py", "business_accounting_capacity.py", "accounting_component_segments.py", "business_accounting_refunds_v2.py", "accounting_joint_ledger.py", "accounting_joint_access.py", "accounting_joint_order.py", "accounting_return_lots.py", "business_accounting_profile.py",
                 "requirements.lock")
WINDOWS_FILES = ("Starten.cmd", "Sicherung_erstellen.cmd", "Sicherung_wiederherstellen.cmd",
                 "Run.cmd", "START_HIER.txt")
OFFLINE_INSTALLER_FILES = ('Python_Umgebung_aktualisieren.cmd', 'Python_Umgebung_aktualisieren.py')
OPERATOR_FILES = ('scripts/reconcile-accounting-restore.py', 'docs/CRM_ERP_EUER_BETRIEB.md',
                  'docs/CRM_ERP_EUER_E1A_API.md', 'docs/CRM_ERP_EUER_E1B1_API.md', 'docs/CRM_ERP_EUER_E1B2_API.md', 'docs/CRM_ERP_EUER_E1B3A_API.md', 'docs/CRM_ERP_EUER_E1B3B_API.md', 'docs/CRM_ERP_EUER_E1B3C_API.md', 'docs/CRM_ERP_EUER_E1B4A1_API.md', 'docs/CRM_ERP_OFFLINE_SERVICEBERICHTE.md', 'docs/CRM_ERP_ENTSCHEIDUNGEN.md', 'docs/CRM_ERP_EUER_WORKFLOW_API.md', 'docs/CRM_ERP_EUER_CLIENTS.md', 'docs/CRM_ERP_EUER_REGELQUELLEN_2026.md', 'docs/CRM_ERP_PERSONAL_WORKFLOW.md', 'docs/CRM_ERP_LOHN_QUELLEN.md', 'docs/CRM_ERP_UNTERNEHMENSEXPORT.md', 'docs/CRM_ERP_LOHN_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_LOHN_CLIENTS.md', 'docs/CRM_ERP_LOHN_MIDIJOB_2026.md', 'docs/CRM_ERP_LOHN_MIDIJOB_CLIENTS.md', 'docs/CRM_ERP_LOHN_ZEITACHSEN_API.md', 'docs/CRM_ERP_LOHN_ANSPRUECHE_GEGENPRUEFUNG_2026.md', 'docs/CRM_ERP_LOHN_ANSPRUECHE_2026.md', 'docs/CRM_ERP_LOHN_ANSPRUECHE_API.md', 'docs/CRM_ERP_LOHN_GESAMTFALL_KERNEL_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_REISE_V3_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_REISE_V3_VERTRAG_2026.md', 'docs/evidence/payroll-travel-policy-clients-2026-11-03.json', 'docs/CRM_ERP_REISE_PAUSCHALSTEUER_CLIENTS.md', 'docs/CRM_ERP_LOHN_ANSPRUECHE_CLIENTS_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_LOHN_ANSPRUECHE_CLIENTS.md', 'docs/CRM_ERP_LOHN_KRANKHEIT_VERSIONEN_2026.md', 'docs/CRM_ERP_LOHN_BERECHNUNGSFAELLE_API.md', 'docs/CRM_ERP_LOHN_GESAMTFALL_GEGENPRUEFUNG_2026.md', 'docs/CRM_ERP_REISE_PAUSCHALSTEUER_GEGENPRUEFUNG_2026.md', 'docs/evidence/travel-clients-2026-11-03.json', 'docs/CRM_ERP_REISEPAUSCHALEN_CLIENTS.md', 'docs/CRM_ERP_REISE_PAUSCHALSTEUER_2026.md', 'docs/CRM_ERP_LOHN_MITARBEITERBELEG_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_LOHN_MITARBEITERBELEG_API.md', 'docs/CRM_ERP_LOHN_MITARBEITERBELEG.md', 'docs/CRM_ERP_LOHN_ZEITACHSEN_CLIENTS_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_LOHN_ZEITACHSEN_CLIENTS.md', 'docs/CRM_ERP_LOHN_FAKTEN_2026.md', 'docs/CRM_ERP_LOHN_FAKTEN_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_LOHN_TEILMONATE_2026.md', 'docs/CRM_ERP_LOHN_TEILMONATE_PRUEFUNG_2026-11-03.json', 'docs/evidence/travel-rates-2026-transcription.json', 'docs/CRM_ERP_REISEPAUSCHALEN_API.md', 'docs/CRM_ERP_LOHN_MIDIJOB_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_ASSISTENT.md', 'docs/CRM_ERP_SPRACHE.md', 'docs/CRM_ERP_DATEIMIGRATION.md', 'docs/CRM_ERP_DATEIIMPORT.md', 'docs/CRM_ERP_ZUSATZFELDER.md', 'docs/CRM_ERP_KONFORMITAET_QUELLEN.md', 'docs/CRM_ERP_ABHAENGIGKEITEN_SICHERHEIT.md', 'docs/evidence/product-source-bom.json', 'docs/evidence/source-advisories-2026-11-03.json', 'docs/CRM_ERP_VERTRIEB.md', 'docs/CRM_ERP_SERVICE.md', 'docs/CRM_ERP_SERVICE_CLIENTS.md', 'docs/CRM_ERP_DATENSCHUTZFAELLE.md', 'docs/CRM_ERP_LOHNZAHLUNGEN_EUER_CLIENTS.md', 'docs/CRM_ERP_BANKABGLEICH_API.md', 'docs/CRM_ERP_BANKABGLEICH.md', 'docs/CRM_ERP_BANKABGLEICH_CLIENTS.md', 'docs/CRM_ERP_BANKABGLEICH_PRUEFUNG_2026-11-03.json', 'docs/CRM_ERP_BANK_EUER_INTEGRATION_PRUEFUNG.md', 'docs/CRM_ERP_BEDIENBARKEIT.md', 'docs/CRM_ERP_BENUTZERHANDBUCH.md', 'docs/CRM_ERP_BETRIEBSMITTEL.md', 'docs/CRM_ERP_BETRIEBSMITTEL_CLIENTS.md', 'docs/CRM_ERP_EINKAUF_RETOUREN.md', 'docs/CRM_ERP_EINKAUF_RETOUREN_API.md', 'docs/CRM_ERP_EINKAUF_RETOUREN_CLIENTS.md', 'docs/CRM_ERP_PROVISIONIERUNG.md', 'docs/CRM_ERP_PROVISIONIERUNG_SICHERHEITSPRUEFUNG.md', 'docs/evidence/accessibility-2026-11-03.json', 'docs/CRM_ERP_LOHNZAHLUNGEN_EUER.md', 'docs/CRM_ERP_LOHNZAHLUNGEN_EUER_API.md', 'docs/CRM_ERP_EUER_KETTEN_ANALYSE.md', 'docs/CRM_ERP_INVENTUR.md', 'docs/CRM_ERP_UNTERNEHMENSUEBERSICHT.md', 'docs/CRM_ERP_ASSISTENT_CLIENTS.md', 'docs/CRM_ERP_LOHN_RECHENWERK_2026.md', 'docs/CRM_ERP_KUNDENARBEITSBEREICH.md', 'docs/CRM_ERP_GERAETEHERKUNFT.md', 'docs/CRM_ERP_PROJEKTWIRTSCHAFTLICHKEIT_CLIENTS.md')
SOURCE_ONLY_NOTICE = '''Smartplan Windows - reines Quell-/Supportpaket

Dieses ZIP enthaelt KEINE Python-Abhaengigkeiten und keinen Offline-Updater.
Es ist kein vollstaendiges Windows-App-/Python-Offlinepaket.
Fuer ein Update der bestehenden privaten Python-3.12-Umgebung bitte das
vollstaendige Smartplan-Office-Windows-Paket desselben 0.12-Updates laden.
Darin muessen python-wheels, backend/requirements.lock und
Python_Umgebung_aktualisieren.cmd zusammen enthalten sein.
Die App und den lokalen Server schliessen, dann den Updater ausdruecklich starten.
Python wird dabei nicht neu installiert; Geschaeftsdaten bleiben ungeoeffnet.
Dieses Quellpaket allein ersetzt keine neue App und keine fehlenden Wheels.
'''


def build(destination, wheels_dir=None):
    files = [("backend/" + name, ROOT / "backend" / name) for name in BACKEND_FILES]
    files.extend((name, ROOT / 'windows' / name) for name in WINDOWS_FILES)
    files.extend((name, ROOT / name) for name in OPERATOR_FILES)
    manifest = None
    if wheels_dir is not None:
        spec = importlib.util.spec_from_file_location('smartplan_offline_installer', ROOT / 'windows' / OFFLINE_INSTALLER_FILES[1])
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        manifest = installer.wheel_manifest(wheels_dir, ROOT / 'backend/requirements.lock')
        files.extend((name, ROOT / 'windows' / name) for name in OFFLINE_INSTALLER_FILES)
        files.extend(('python-wheels/' + name, Path(wheels_dir) / name) for name in manifest['files_sha256'])
    contents = [(name, source.read_bytes()) for name, source in files]
    if manifest is None:
        contents.append(('QUELLPAKET_HINWEIS.txt', SOURCE_ONLY_NOTICE.encode('utf-8')))
    else:
        contents.append(('python-wheels/WHEELS_SHA256.json', (json.dumps(manifest, indent=2, sort_keys=True) + '\n').encode('utf-8')))
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in sorted(contents):
            if name.endswith((".cmd", ".txt")):
                value = value.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
            info = zipfile.ZipInfo("Smartplan_Windows_Start_und_Sicherung/" + name, (2026, 10, 20, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, value)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_suffix(destination.suffix + ".sha256").write_text(digest + "  " + destination.name + "\n", encoding="ascii")
    print(destination.name, destination.stat().st_size, "bytes", digest)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', nargs='?', type=Path, default=ROOT / 'downloads/Smartplan_Windows_Start_und_Sicherung.zip')
    parser.add_argument('--wheels-dir', type=Path, help='Vollstaendige Windows-x64/Python-3.12-Wheels aus backend/requirements.lock')
    options = parser.parse_args()
    build(options.destination, wheels_dir=options.wheels_dir)
