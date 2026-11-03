# Eigene EÜR im Browser

Stand: 03.11.2026. Implementierter Browserablauf für das additive EÜR-Journal. Die fachlichen Regeln, unterstützten Sachverhalte und Backendgrenzen stehen in `CRM_ERP_EUER_WORKFLOW_API.md` und `CRM_ERP_EUER_REGELQUELLEN_2026.md`. Dies ist kein Nachweis einer amtlichen Steuererklärung oder eines vollständigen Unternehmensjahres.

## Zugang und Bedienung

Unter **Finanzen → EÜR-Vorbereitung → Eigene EÜR** führt eine gemeinsame Ansicht von Quellen und fachlicher Prüfung zu Journal, Anlagen, Monatsperioden und Jahresausgabe. **Geldflüsse vorbereiten** führt zurück zum vorhandenen Vorjournal; Quellnachweise öffnen die bestehenden Zahlungs- und Belegaufteilungen. Das Unternehmensprofil bleibt über **Unternehmensprofil und Gültigkeit** erreichbar. Unbekannte Gültigkeitsdaten bleiben leer; weder historische Startdaten noch SKR04-Konten werden vorausgefüllt.

Die Oberfläche unterstützt diese ausdrücklichen Entscheidungen:

- Bestehende vollständige CashEvents anhand ihrer tatsächlichen dokumentarischen C1/C2/R1/R2-Centanteile einordnen. Pro Anteil werden betrieblicher Netto-/Steueranteil, abziehbare Kosten, bezahlte abziehbare Vorsteuer und als Kosten abziehbare Steuer getrennt geprüft. Bruttobeträge werden nicht neu mit 19 % geteilt.
- Vorsteuerrecht eines geprüften Originalbelegs anhand Rechnungseingang und Leistung beziehungsweise belegter vollständiger Vorauszahlung beurteilen. Ein tatsächlicher Abzug von 0,00 muss ebenfalls ausdrücklich erfasst werden.
- Belegte Steuerzahlungen/-erstattungen, Geldeinlagen/-entnahmen und Darlehenshauptbeträge an Original, Geldkonto und eindeutige Zahlungsnachweis-ID binden. Es wird keine Zahlung ausgelöst.
- Neue belegte Anlagegüter mit ausdrücklich gewählter linearer Nutzungsdauer erfassen und die vom Server errechnete Jahres-AfA prüfen.
- Aktive Buchungen atomar berichtigen oder exakt gegenbuchen; frühere Einträge und Quellen bleiben im Journal lesbar.
- Monatsperioden nach Kontoabgleich, Originalprüfung und Sonderfallprüfung schließen beziehungsweise begründet wieder öffnen.
- Den Jahresstand als eigenes unveränderliches JSON-/CSV-Prüfpaket festhalten und lokal herunterladen.

Jede wirtschaftliche Entscheidung führt zuerst zu einer unverbindlichen Vorschau. Die Vorschau zeigt die getrennten EÜR-, Umsatzsteuer-, neutralen und gegebenenfalls nicht abziehbaren Wirkungen, die zugrunde liegenden Quellen sowie Begründung und Nachweis. Erst eine zusätzliche ausdrückliche Bestätigung schreibt das Journal.

Ungeprüfte Eingangsdokumente können aus der Quellenliste fachlich geprüft werden. Belegprüfung und Vorsteuerentscheidung bleiben getrennte Schritte. Fehlende Zahlungsimporte und Beleganteile verweisen auf die bestehenden Finanzfunktionen. Nicht unterstützte Sonderfälle bleiben durch die Serverprüfung offen; die Oberfläche behauptet dafür keine allgemeine Steuerautomatik.

## Rechte, Wiederholung und nachvollziehbare Ausgabe

Globale `accounting.read` und `finance.read` sind Voraussetzung zum Lesen. Schreiben benötigt zusätzlich `accounting.prepare`, `accounting.admin` und `finance.write`, einen aktiven Finanzbetrieb und die Serverfreigabe. Vor geschützten Bestätigungen und Wiederholungen werden globale Rechte und aktueller EÜR-Status erneut gelesen. Originalprüfungen benötigen außerdem `finance.approve`. Eine bekannte Quellen- oder Leserechtsverweigerung entfernt die offene Detailansicht.

Noch ungesendete Formulare bleiben innerhalb der Sitzung an genau ihren Quellenhash gebunden; eine geänderte dokumentarische Aufteilung übernimmt alte Centfelder nicht stillschweigend für andere Anteile. Bei verlorener oder unpassender Bestätigung bleibt der ursprüngliche Auftrag im Arbeitsspeicher derselben angemeldeten Browsersitzung erhalten. Die Wiederholung verwendet identische Eingaben und dieselbe Vorgangskennung. Der Empfangsnachweis wird vor dem Entfernen des offenen Auftrags gegen Vorschau und eingefrorene Eingaben geprüft, einschließlich Gegenbuchungen, Periodenprüfung und Exportinhalt. Mehrdeutige 403-/404-/409-Antworten löschen den Auftrag nicht; ein ausdrücklich als nicht angenommen bestätigter Konflikt erlaubt eine neue Prüfung.

Jahresberichte zeigen den bestätigten Buchführungsbeginn, offene Quellen und getrennte bestätigte Zwischenwerte. Bei offenen Fällen bleiben EÜR-Ergebnis beziehungsweise Umsatzsteuersaldo ausdrücklich nicht verfügbar. Erfasste Geldkontobewegungen enthalten keine erfundenen Anfangs- oder Endsalden. Im bisherigen Auszahlungsbereich erscheinen im EÜR-Journal gebundene Steuer-/Kapitalzahlungsoriginale ausdrücklich als Zahlungsnachweise ohne Lieferantenverbindlichkeit. Fehlende Auszahlungs-/Restbeträge werden für diese Quelle nicht als gewöhnliche offene Lieferantenrechnung angezeigt. In der EÜR-Quellenliste bleiben für solche Zahlungsnachweise nur externe Geldbewegungen verfügbar; Vorsteuer- und Anlageaktionen entfallen. Nach einer Gegenbuchung bleibt dieser Quellenzweck reserviert, und die erforderliche erneute Einordnung wird ausdrücklich angezeigt. Ein gespeichertes Prüfpaket wird vor der Dateiausgabe auf seine kanonische Berichts- und CSV-Prüfsumme geprüft. Die Ausgabe ist weder eine ELSTER-Übermittlung noch ein zertifizierter DATEV-Import.

## Geprüfter Browserablauf

Elf neue Node-Tests prüfen Centgenauigkeit, fehlende Rechte und Schreibfreigaben, keine vorgegebenen Abzugsquoten/Konten/Startdaten, Quelle-/Unitbindung, Vorschau-/ACK-Konsistenz einschließlich Periodenkontrolle, unveränderte Wiederholung bei verlorener oder verweigerter Antwort, die eindeutige Nichtannahme, unvollständige Jahresergebnisse und die Abgrenzung gebundener Zahlungsnachweise von Lieferantenverbindlichkeiten. Zusammen mit den bestehenden Accounting- und Projektwirtschaftlichkeitstests bestehen **36 gezielte Node-Tests**.

Ein separater echter Chromium-Ablauf verwendet MFA-Anmeldung, den tatsächlichen HTTP-/Flask-/Domainweg und eine wegwerfbare lokale SQLite-Datenbank mit synthetischen dokumentierten Quellen. Das bestehende Testinstrument für synthetische Rechnungsarchive erzeugt nur die Ausgangsbelege; die EÜR- und Profilentscheidungen laufen vollständig durch die Browseroberfläche. Der Ablauf umfasst:

1. Leeres Profil öffnen und Regelbesteuerung/Ist sowie tatsächliche synthetische Gültigkeitsdaten ausdrücklich bestätigen.
2. Inländischen Erlös einordnen; nach tatsächlicher Speicherung die Antwort verlieren und denselben Auftrag unverändert wiederholen.
3. Vorsteuerrecht und bezahlten Aufwand getrennt bestätigen, die Kostenart anschließend berichtigen.
4. Eine tatsächlich belegte Umsatzsteuerzahlung erfassen.
5. Anlage, bezahlte Vorsteuer und lineare AfA getrennt buchen, AfA gegenbuchen und erneut prüfen.
6. Monatsperiode schließen und begründet wieder öffnen.
7. Jahresstand einfrieren, JSON und CSV herunterladen und die ausgegebenen Inhalte prüfen. Der synthetische Fall endet mit **−173,33 EUR** für die erfassten Quellen; dieser Betrag ist kein reales Unternehmensergebnis.
8. Desktop und 390-Pixel-Ansicht ohne horizontalen Seitenüberlauf prüfen.

Der Chromium-Prozess läuft mit aktivierten Namespace-, PID-, Netzwerk- und Seccomp-Sandboxen. Loopback-Origin-/Proxyanpassung ist ausschließlich Testinfrastruktur; produktives TLS, PostgreSQL-Laufzeitrollen, amtliche Übermittlung und physische Mobilgeräte sind nicht Gegenstand dieses Browsernachweises.

Dateien und Nachweise:

- Produkt: `web/office/accounting-euer.js`; schmale Einbindung in `web/office/office.js`.
- Tests: `web/office/tests/accounting-euer.test.mjs`, `accounting-euer-flow.cjs`, `accounting-euer-e2e.cjs`, `accounting-euer-fixture.py`.
- Node-Protokoll: `work/verification/accounting-euer-node-regression.log`.
- Browser-Protokoll: `work/verification/accounting-euer-browser-final.log`.
- HTTP-Nachweise und Screenshots: `work/verification/accounting-euer-browser-previews/`.

Ausführung vom Repositoryhauptverzeichnis:

```sh
node --test --test-isolation=none web/office/tests/accounting-euer.test.mjs web/office/tests/accounting.test.mjs web/office/tests/project-economics.test.mjs
SMARTPLAN_BROWSER_TEST_PYTHON="$PWD/backend/.venv/bin/python" SMARTPLAN_BROWSER_NAMESPACE_SANDBOX=1 SMARTPLAN_BROWSER_SCREENSHOT_DIR="$PWD/work/verification/accounting-euer-browser-previews" node web/office/tests/accounting-euer-e2e.cjs
```

Der EÜR-Browserrunner ist ein eigener Einstiegspunkt. Der bisherige `SMARTPLAN_BROWSER_WORKFLOW`-Selektor des gemeinsamen End-to-End-Runners wurde dafür nicht verändert.
