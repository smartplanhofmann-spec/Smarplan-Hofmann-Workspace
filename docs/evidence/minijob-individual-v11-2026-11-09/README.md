# Nachweis des begrenzten individuellen Minijobs v11

Der Backendkandidat rechnet einen belegten vollen Monat 2026 mit 175–603 EUR, Steuerklasse I/V, beitragsfreier gesetzlicher Familienversicherung und jeweils belegter RV-Pflicht oder -Befreiung. Die tatsächliche GKV bleibt erhalten; technisches PAP-PKV=1 folgt der getrennt dokumentierten BMF-Anweisung. Der [Vertrag](../../CRM_ERP_MINIJOB_INDIVIDUELL_V11_2026.md) beschreibt die Grenzen und Pflichtoriginale.

Ausgeführt und bestanden:

- 36 unabhängige XML/Java-Steuervektoren; alle 32 vorherigen 2026-Kerneldateien bytegleich.
- 26 Domain-/Jahresbasisprüfungen, darunter 11 neue V11-Fachketten und unveränderte historische Jahresfälle.
- 25 bestehende Account-/Gesamtfall-/V10-Regressionen.
- Vier echte PostgreSQL-/MFA-/HTTP-Fälle: private Originale, neue Rechteprüfung nach Anmeldung/Neustart, Cash/EÜR und vollständiges Dump/Restore, identische konkurrierende Laufannahme sowie zwei unterschiedliche gleichzeitige Altfalkorrekturen.
- Ein zusätzlicher echter HTTP-Nachlauf mit ungültigen Unicode-Prüftexten und unstrukturierten Identitätsdetails (400).
- 16 Paketprüfungen, einschließlich des Imports des tatsächlich erzeugten Windows-Supportarchivs. Die neue Berechnung und Quellenauflösung stehen in beiden Paketlisten und der Windows-CI-Liste.

Die verworfenen Erstläufe bleiben unverändert erhalten. Der erste Domainlauf fand fehlende V11-Render-Metadaten; der erste Migrationstest erwartete fälschlich einen Zufluss ohne Zahlung; die erste Paketprüfung fand nur die fehlende Python-Umgebung in der eigenen Arbeitskopie. Ursachen und finale Gegenbeweise sind getrennt im Manifest vermerkt. Eine unabhängige Codeprüfung fand außerdem eine neue Typabfrage vor der ursprünglichen Struktursperre; `details=null/int/bool/list/string` liefert wieder 400 und wird tatsächlich über HTTP geprüft.

Reproduzierbare lokale Prüfung:

```sh
PYTHONPATH=backend python -m unittest test_payroll_individual_minijob test_business_payroll_annual_basis -v
PYTHONPATH=backend python -m unittest test_business_payroll_accounts test_business_payroll_calculation_cases test_payroll_factor_taxfree_travel -v
python -m unittest discover -s scripts -p test_native_release.py -v
```

Der PostgreSQL-Satz heißt `online.test_business_payroll_individual_minijob_pg`; er benötigt die vorhandene Testkonfiguration mit einer ausdrücklich entbehrlichen lokalen PostgreSQL-Datenbank. Der Test setzt diese Datenbank zurück. Hier wurde ausschließlich der eigene kurzlebige Container auf Port 32781 verwendet.

Die echte synthetische gemeinsame Fixture wurde durch `scripts/generate-individual-minijob-fixture.py` erzeugt. Sie enthält Pflicht-/Befreiungsfall und die explizite v5→v11-Korrektur samt alten und neuen Originalen. Alle Datei-/Ausgabehashes stehen in `manifest.json`. Browser-/App-Integration, verbundene CI und tatsächliche Windows-/iPhone-Abnahme sind keine Behauptungen dieses Backendnachweises.
