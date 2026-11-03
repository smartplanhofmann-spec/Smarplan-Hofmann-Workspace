# Lohnzahlungen → EÜR: Clientabnahme

Stand 03.11.2026. Browser und Flutter unterstützen die tatsächlichen, bereits belegten Zahlungen des [API-Vertrags](CRM_ERP_LOHNZAHLUNGEN_EUER_API.md). Der Einstieg liegt unter Personal → Lohnberechnung → Belegte Lohnzahlungen. Die öffentliche Einordnung erfolgt separat unter Finanzen → EÜR-Vorbereitung → Eigene EÜR.

Die private Auswahl bindet Person, Unternehmensinstanz, aktuelle Quellfassung und einzelne tatsächliche Zahlungsteile. Neue Teile sind nicht vorausgewählt. Bei Abführungen bleiben alle fünf Betragsfelder einschließlich bekannter Nullwerte, Zahlungstag, Referenz, Gesamtbetrag und Originalauswahl leer, bis sie ausdrücklich eingegeben werden. Berechnete Obergrenzen sind nur Hinweise. Negative Arbeitnehmerzahlungsteile bleiben tatsächliche Zuflüsse. Historische Fassungen und geprüfte Originaldateien bleiben lesbar; neue Nachweiskorrekturen benötigen ein privates Original. Eine Aufhebung behält das ursprüngliche Geldkonto und behauptet keine Rückzahlung.

Die allgemeine EÜR erhält ausschließlich die aggregierte öffentliche Finanzquelle. Geldbetrag, Datum, Richtung und Kategorien sind unveränderlich; SKR04-Konten und Prüfgrund werden ausdrücklich eingegeben. Personalrechte sind dafür nicht erforderlich. Geänderte Nachweise verlangen eine eigene EÜR-Berichtigung. Alte Quellen und Journalfassungen bleiben unverändert.

Vor Schreiben, Wiederholung und Originaldownload werden aktuelle Rechte, Modulmodus und Instanz neu geprüft. Eine verlorene Antwort bleibt als exakter ursprünglicher Auftrag samt Kennung erhalten, auch bei späterer Rechte- oder Restore-Sperre. Originaldownloads prüfen vollständige Bytes, Größe und SHA-256. Offene private Ansichten werden beim Rechte-/Sitzungswechsel ausgeblendet.

## Ausgeführte Prüfungen

Alle Daten und Originale sind synthetisch. Es wurde weder überwiesen noch eine amtliche Meldung oder externe Nachricht erzeugt.

| Prüfung | Ergebnis | Nachweis |
|---|---:|---|
| Node: PayrollCash und vorhandene EÜR-Verträge | 20/20 | Ausdrückliche Teilwahl/Abführungen, öffentliche Datensparsamkeit, Betragssummen, negative Teile, Vorschau-/Quittungsbindung, Originalbytes, Rechteentzug und unveränderter Replay |
| Flutter: PayrollCash und vorhandene EÜR | 17/17 | Fachverträge, Sitzung/Wiederholung, leere Abführungsfelder, private Ansichten bei Rechteentzug und mobile EÜR |
| Flutter Analyze | Ohne Befund | Vollständiger aktueller App-Quellstand |
| Echter Chromium-Browser | Bestanden | MFA/HTTP, vollständiger vorgelagerter Payrollablauf, zwei Nettozahlungsteile, ausdrücklich belegte Abführung, Originaldownload, verlorene Übernahme- und EÜR-Antworten, Nachweisaufhebung/EÜR-Berichtigung, unveränderte Altquelle, Buchhalter ohne Personalrecht mit tatsächlicher EÜR-Bedienung, 390px-Ansicht |

Der gezielte Browserlauf isoliert die Finanzquellen im temporären Fixture. Fremde, ursprünglich unzugeordnete Zahlungen aus anderen Testfällen würden die vollständige EÜR-Quellenliste für den Buchhalter berechtigt sperren; Produktionsrechte wurden dafür nicht gelockert. Chromium lief mit geprüfter Namespace-, PID-, Netzwerk- und Seccomp-Isolation.

Reproduzierbare Tests: `web/office/tests/payroll-cash.test.mjs`, `app/test/business_payroll_cash_test.dart`, `web/office/tests/payroll-cash-flow.cjs`; echte Backend-Fixturedaten unter `app/test/fixtures/payroll_cash.json`. Browserstart über `SMARTPLAN_BROWSER_WORKFLOW=payroll-cash node web/office/tests/e2e.cjs`. Lokale Protokolle: `work/verification/payroll-cash-{node,flutter,analyze,browser}.log`; Screenshots und synthetische Aufträge unter `work/verification/payroll-cash-browser/`.

Die [fachlichen Grenzen des Backends](CRM_ERP_LOHNZAHLUNGEN_EUER.md) gelten unverändert: tatsächliche Zahlungen 2026, keine automatisch erzeugten Geldflüsse, keine Jahreswechsel-/Zehntagesfälle oder ungestützten Lohnsonderfälle. Die Abnahme ersetzt keine externe fachliche oder gerätespezifische Nutzerabnahme.
