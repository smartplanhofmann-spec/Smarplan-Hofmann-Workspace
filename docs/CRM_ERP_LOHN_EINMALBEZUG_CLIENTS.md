# Einmalbezug im Browser und in der nativen Anwendung

Stand: 4. November 2026. Dieser Vertrag beschreibt den im Repository implementierten Client-Teil der Source4/v6-Lohnberechnung. Er ist kein Nachweis für die Fertigstellung des gesamten CRM-/ERP-Ziels.

## Bedienweg und Originalquellen

Im Personalbereich führt **Lohnberechnung 2026 → Einmalbezugsfälle aus Jahresquellen öffnen** zum konkreten Zuflussmonat. Die Auswahl bleibt ausdrücklich beim Benutzer:

1. Unveränderter laufender Gesamtfall des Monats aus Source3/v5.
2. Konkreter Einmalanspruch mit geplantem tatsächlichem Zuflusstag.
3. Vollständige aktuelle Jahresbasis, die genau diesen laufenden Gesamtfall enthält.
4. Gegebenenfalls belegte Vorjahresbasis für die Märzklausel.
5. Jahressteuergrundlage ohne den aktuellen Einmalanspruch sowie geschützte Originale und Prüfvermerk.

Ein berechenbarer, bestätigter Einmalbezugsfall kann unmittelbar in einen Lohnlauf übernommen werden. Browser und Flutter senden dafür ausschließlich `source_schema_version: 4`, `employee_id` und die unveränderliche `one_off_case_ref` aus Kennung, Revision und Inhaltsprüfsumme. Die Vorschau muss diese Referenz, den eingebetteten laufenden Originalfall und die gesamte berechnete Zusammensetzung bestätigen. Unbekannte oder widersprüchliche Quellen bleiben gesperrt.

Die Anzeige trennt laufenden Lohn, Einmalanspruch, Steuerjahr, SV-Beitragsjahr, einzelne Einmalbeitragsbasen und zusätzliche Lohnsteuer, Solidaritätszuschlag und Kirchensteuer. Laufender Reiselohn und bereits belegte Nettoabzüge bleiben enthalten; sie werden nicht nochmals zugeschlagen. Die native Aktion **Eingaben erneut prüfen** prüft dieselbe Source4-Fassung erneut und öffnet keinen freien Bruttoeditor.

## Freigabe, Korrektur und verlorene Antwort

Der Benutzer bestätigt den geprüften Berechnungsumfang ausdrücklich. Eine Vorschau oder ein gespeicherter Fall löst keine Zahlung und keine amtliche Übermittlung aus.

Existiert für den Monat bereits ein Lohnlauf, führt die Übernahme des Einmalbezugs zu einer begründeten Korrektur derselben Laufkennung. Das gilt auch für einen bereits bezahlten v5-Lauf. Ein v6-Lauf kann nur mit demselben ursprünglichen Einmalanspruch berichtigt werden. Die Empfangsprüfung bindet Quellen, Umfang, vorherigen Hash, vollständige Differenz, PDF-Prüfsumme und Korrekturgrund an den ursprünglichen Auftrag.

Geht die Erfolgsantwort verloren, bleibt der ursprüngliche Auftrag im privaten Sitzungszustand offen. Wiederholung verwendet identische Werte und Vorgangskennung und behält die ursprüngliche Empfangsprüfung. Ein neuer Fall oder eine abweichende Berechnung ersetzt den offenen Auftrag nicht. Aktuelle Lese-/Freigaberechte werden erneut geprüft. Die native Hauptansicht bindet Ergebnisse an das konkrete Sitzungsobjekt, den Mitarbeiter und die Ansichtskennung; gleiche Generationsnummern verschiedener Sitzungen reichen nicht. Sitzungs-/Mitarbeiterwechsel, Rechteentzug, Hintergrundwechsel und Entfernen der Hauptseite schließen auch verschachtelte private Editoren. Verspätete Ergebnisse und private Fehlermeldungen dürfen diese Ansichten nicht wiederherstellen.

Fall- und Laufhistorien bewahren die Originalfassungen. Die tatsächliche Fallhistorienantwort enthält `{items: [...]}`; ihre Mitarbeiter-, Fall- und Revisionsbindung wird je Originaleintrag geprüft. Ein erfundener zusätzlicher Mitarbeiter-Wrapper wird nicht verlangt. Eine spätere Fallaufhebung ändert bereits gespeicherte Lohnläufe nicht rückwirkend.

## Zahlung, Jahresübersicht und Mitarbeiterbeleg

Der normale Lohnkonto-Editor übernimmt auch v6-Läufe. Ein Source4-Zahlungsnachweis muss den bestätigten Lauf, den vollständigen Barbetrag nach Nettoabzügen und den tatsächlichen Zuflusstag belegen. Bereits nachgewiesene Zahlungsteile bleiben bei einer Korrektur unverändert; ein zusätzlicher Teil belegt nur die tatsächliche Differenz. Die Clients erfinden für Source4 keinen Nullzahlungsnachweis. Die separat belegte Source3-Nullnetto-Funktion bleibt erhalten.

Jahresübersicht und historische PDF-/JSON-Ausgaben unterstützen die v6-Rechnung. Jahressummen verwenden nur die wirksame Monatsfassung und addieren die Korrekturhistorie nicht erneut. Heruntergeladene Dateien werden gegen den gewählten historischen Stand und seine Prüfsumme geprüft.

Mitarbeiter erhalten den engen Belegvertrag **Schema 3**: Einmalbetrag, Zuflussstichtag, Steuer-/SV-Jahr, Märzklausel und eigene zusätzliche SV-/Steuerbeträge. Jahresprognosen, private Anspruchskennungen, Jahresbasis, Quellenhashes und Personaloriginale bleiben außerhalb dieses Vertrags und seines eigenständig gerenderten PDFs. Alte Belegschemata 1/2 behalten ihre historischen Leser und PDF-Bytes. Einzelheiten und unabhängige Own-Rollenprüfungen stehen in [payroll-oneoff-own-statements-2026-11-04.md](payroll-oneoff-own-statements-2026-11-04.md).

## Prüfnachweise

Maschinenlesbares Ergebnis: [payroll-oneoff-clients-2026-11-04.json](evidence/payroll-oneoff-clients-2026-11-04.json). Dauerhafte Protokolle und Browserbilder liegen unter `docs/evidence/payroll-oneoff-clients-2026-11-04/`.

Die echte Domain-Fixture `app/test/fixtures/payroll_oneoff_runs.json` enthält den ursprünglichen v6-Lauf, eine Änderung des Bonus von 500,00 auf 700,00 Euro und die Übernahme eines tatsächlich bezahlten v5-Laufs. Node und Dart prüfen jeweils Originalidentität, vollständige Differenz, erhaltene erste Zahlung und zusätzlichen tatsächlichen Differenzbetrag. Der ursprüngliche Fall enthält 4,00 Euro pauschalen Reiselohn und 1,09 Euro Arbeitnehmer-Nettoabzug; beide dürfen durch den Einmalbezug nicht verschwinden oder doppelt erscheinen.

Der Chromium-Test läuft mit echter MFA, HTTP und einer wegwerfbaren Datenbank. Er durchläuft Originalauswahl, Fallfreigabe mit verlorener Antwort, Fallkorrektur, produktiven Source4-Lauf mit verlorener Antwort, Laufkorrektur, PDF/JSON, tatsächlichen Zahlungseditor, Jahresübersicht, engen Mitarbeiterbeleg und Fallhistorie. Namespace-, PID-, Netzwerk- und Seccomp-Sandbox werden vor Anwendungskontakt nachgewiesen. Der eigene Beleg wird in diesem Test aus dem Personalzugang geöffnet; echte Own-Rollen-Sperren für private Routen werden zusätzlich unabhängig im Backend geprüft.

Das Browsermodul `payroll-oneoff-own-flow.cjs` ist Teil des registrierten Workflows `payroll-oneoff-cases`; es benötigt keine zusätzliche Workflowregistrierung. Eingeschränkte frühere Node-Läufe mit bloßer Dateizählung gelten nicht als Anzahl tatsächlich ausgeführter Testfälle. Das endgültige Node-Protokoll enthält benannte Einzeltests aus einem Prozesslauf mit funktionierender Testisolation.

## Verbleibende fachliche Grenzen

Ein Client kann nur einen vom Kernel vollständig freigegebenen konkreten v6-Fall abschließen. Fehlende Jahresnachweise, nicht unterstützte Versicherungs-/Steuerfälle und ungeklärte Zuordnungen werden nicht aus Monatswerten geschätzt. Auf mehrere voneinander abweichende tatsächliche Zahlungstage zu verteilende Einmalbezüge benötigen den gesonderten belegten Zuordnungsweg; die Anwendung ersetzt diese Tage nicht durch einen angenommenen Stichtag. Amtliche Systemzulassung, Übermittlung und tatsächliche Bankausführung werden durch diese Clientprüfung nicht behauptet.
