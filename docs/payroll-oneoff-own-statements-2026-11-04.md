# Eigene Lohnnachweise für Einmalbezüge – Stand 04.11.2026

Der vorhandene Mitarbeiter-Belegbereich unterstützt bestätigte Source4-Läufe mit `de_2026_oneoff_composition_v6`. Die neue Belegfassung 3 ergänzt die bisherigen eigenen Anspruchs-, Reise- und Nettoabzugsbeträge um eine begrenzte Einmalzahlungsübersicht. Schema 1 (ältere Läufe) und Schema 2 (v5) bleiben lesbar; ihre ursprünglichen PDF-Bytes bleiben unverändert.

## Anforderungen und Umsetzung

- **Eigener Einmalbezug:** Brutto, berechneter Zuflussstichtag, Steuerjahr, SV-Zuordnungsjahr, Märzklausel, fünf eigene SV-Beiträge und eigene Lohnsteuer/Soli/Kirchenlohnsteuer werden positiv ausgewählt. Browser, Flutter und eigener PDF-Nachweis zeigen dieselben Beträge. Ein berechneter Zuflussstichtag oder Auszahlungsbetrag wird weiterhin ausdrücklich nicht als Zahlungsnachweis ausgegeben.
- **Private Jahresquellen:** Die Projektion enthält keine Jahresprognosebeträge, Vorjahresoriginale, jährlichen Beitragsgrundlagen, Anspruchs- oder Quellenreferenzen, Prüfvermerke, Profile oder Personaloriginale. Neue unbekannte Felder innerhalb der Einmalzahlungsübersicht und ihrer SV-Unterstruktur werden von beiden Clients abgelehnt, auch mit neu berechneter Prüfsumme.
- **Originalbezug:** Liste, Einzelbeleg, Historie und PDF müssen für Source4 den tatsächlichen Laufverbrauch und die tatsächliche Reisesteuerverbuchung über `_verify_calculation_record` prüfen. Fehlt die unveränderliche Anspruchsverbrauchszeile, sind diese aktuellen Belegwege gesperrt. Die ältere v5-Fassung bleibt einzeln lesbar.
- **Rechenbezug:** Belegfassung, Regelstand und Berechnungsumfang sind ausdrücklich gebunden. Eigenes Entgelt, steuerpflichtiger Reiselohn, Sachbezug und Einmalzahlung müssen das Gesamtbrutto ergeben. Nettoabzüge, Auszahlung, einzelne SV-Beiträge, Jahrsplit und Steuersummen werden geprüft. Die Clients berechnen keine neuen privaten Jahresgrundlagen.
- **Historie und Rechte:** Ein echter v5-Lauf wird im Domain-Test durch denselben Source4-Lauf korrigiert. Ursprünglicher eigener Beleg und PDF bleiben identisch. Eigener Technikerzugang, fremde Person und entzogenes `time.own` werden geprüft. Private Lauf-, Einmalfall-, Jahresquellen- und Originaldatei-Routen bleiben für den eigenen Techniker gesperrt.

## Nachgewiesene Tests

| Prüfung | Ergebnis |
| --- | --- |
| Backend v1–v6 einschließlich tatsächlicher HTTP-Anfragen, Originaldownload-Verweigerung, Verbrauchsverlust und historischer PDF-Hashes | 17 Tests bestanden |
| Browser-JavaScript-Verträge v4/v5/v6 einschließlich unabhängig erzeugter PDF-Bytes und erneut gehashter Manipulationen | 9 Tests bestanden |
| Flutter-Verträge und Widgetabläufe v4/v5/v6 | 10 Tests bestanden |
| Dart-Analyse der geänderten Bibliothek und neuen Tests | Keine Befunde |
| Syntax des ergänzten Browser-Ablaufhelpers | Bestanden |
| Tatsächlicher integrierter Chromium-Source4-Ablauf einschließlich begrenztem Mitarbeiterbeleg, PDF, Historie und 390-Pixel-Ansicht | Bestanden; Browser-Sandbox vor Zugriff geprüft |

Der Flutter-Widgettest läuft bei 390 × 844 Pixeln über den bestehenden Lohnberechnungseinstieg. Er prüft Einmalzahlungsanzeige, v5-Historie, das Ausbleiben privater Quellenanfragen und das Entfernen der Anzeige nach Freigabeentzug. Hier verwendet der Widgettest einen kontrollierten Transport mit tatsächlich aus dem Backend erzeugten Belegen; die echten Benutzer- und HTTP-Rechte werden separat gegen den lokalen Backendserver getestet.

Die gemeinsame Fixture `app/test/fixtures/payroll_statements_v6.json` wird durch `scripts/generate-payroll-oneoff-statement-fixture.py` aus tatsächlich gespeicherten synthetischen Quellen, Annahmen und Läufen erzeugt. Der Oktoberfall enthält 500,00 EUR Einmalzahlung, 108,75 EUR zusätzliche Arbeitnehmer-SV und unverändert 1,09 EUR belegten Nettoabzug; der Auszahlungsunterschied zur ursprünglichen v5-Fassung beträgt 391,25 EUR. Ein zweiter tatsächlich bestätigter Januarfall zeigt Steuerjahr 2026 und SV-Zuordnung 2025 mit Märzklausel und 2.000,00 EUR Einmalzahlung.

Die frühe Schema1-JSON-Fixture sortiert Objektschlüssel. Für ihren PDF-Hashvergleich stellt der Test die feste Reihenfolge der fünf Beiträge aus `project()` wieder her. Der alte und der aktuelle Renderer erzeugen danach dieselben ursprünglichen Bytes; die historischen Fixture-Dateien wurden nicht verändert.

## Reproduktion und Belege

Aus dem Hauptverzeichnis:

```sh
PYTHONPATH=backend:backend/online /tmp/smartplan-backend-verified/bin/python -m unittest backend.test_business_payroll_statements backend.test_business_payroll_statements_v5 backend.test_business_payroll_statements_v6 -v
node --test --test-isolation=none web/office/tests/payroll-statements.test.mjs web/office/tests/payroll-statements-v5.test.mjs web/office/tests/payroll-statements-v6.test.mjs
```

Aus `app/`:

```sh
PATH=/workspace/toolchains/clang-19/bin:$PATH PUB_CACHE=/workspace/toolchains/pub-cache /workspace/toolchains/flutter/bin/flutter test --no-pub test/business_payroll_statements_test.dart test/business_payroll_statements_v5_test.dart test/business_payroll_statements_v6_test.dart
/workspace/toolchains/flutter/bin/dart analyze lib/business_payroll_statements.dart test/business_payroll_statements_v6_test.dart
```

HTTP- und Fluttertests benötigen einen lokalen Loopback-Testsocket. Die finalen Protokolle und SHA256-Werte stehen unter [evidence/payroll-oneoff-own-2026-11-04](evidence/payroll-oneoff-own-2026-11-04/manifest.json).

Der Browserhelper `web/office/tests/payroll-oneoff-own-flow.cjs` wurde im tatsächlichen Source4-Browserlauf erfolgreich ausgeführt. Eine angemeldete Person mit Personalrechten öffnet darin über den vorhandenen Lohnberechnungseinstieg den begrenzten Mitarbeiter-Lohnnachweis. Geprüft werden echte Schema3-JSON-Antworten, der unabhängige PDF-SHA256, fehlende private Jahres-/Originalkennungen, die ursprüngliche Beleghistorie sowie die 390-Pixel-Ansicht ohne horizontalen Überlauf. Nach dem Wechsel in diesen Belegbereich erfolgen keine privaten Lauf-, Profil-, Jahres-, Einmalfall- oder Personaloriginalanfragen. Der vorherige Personalbereich wird vor Beginn dieser Anfrageprüfung vollständig geladen; dessen notwendige private Verwaltungsanfragen gehören nicht zum Mitarbeiter-Belegabruf.

Dieser Browserlauf verwendet den Personalzugang. Die tatsächliche Berechtigung eines ausschließlich eigenen Technikerzugangs und die Verweigerung privater Quellen und Originaldateien mit HTTP 403 werden unabhängig durch die oben aufgeführten Backend-HTTP-Tests belegt. Der erfolgreiche Browserlauf ersetzt diese Rechteprüfung nicht.

Der [Chromium-Nachweis](evidence/payroll-oneoff-own-2026-11-04/browser.txt) umfasst auch den übergeordneten Source4-Lauf mit Bestätigung, Korrektur und unveränderter Wiederholung einer verlorenen Antwort. Die [mobile Belegansicht](evidence/payroll-oneoff-own-2026-11-04/browser-mobile.png) zeigt den 500,00-EUR-Einmalbezug und 108,75 EUR eigene SV-Beiträge. Namespace-, PID-, Netzwerk- und Seccomp-Sandbox wurden vor dem Anwendungszugriff geprüft. Dieser Teilnachweis ist keine Fertigstellungsaussage für das gesamte CRM/ERP und keine amtliche Meldung.
