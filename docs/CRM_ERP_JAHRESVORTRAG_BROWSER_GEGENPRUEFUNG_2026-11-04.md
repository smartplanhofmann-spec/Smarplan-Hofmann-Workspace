# Unabhängige Browsergegenprüfung: Jahresvortrag V1

Stand: 2026-11-04. Prüfbaum `/workspace/smartplan-opening-year-values-20261104`. Geprüft wurde der ausdrücklich eingefrorene Browserstand des Owners; dieser Review änderte keinen Produktcode und führte weder PostgreSQL-Prüfungen noch einen eigenen Chromiumlauf aus.

## Ergebnis und genaue Reichweite

**30 eigene Fälle bestanden**: vier Vertragsfälle und 26 Ablauf-/Rechtefälle. Der abschließende eigene Lauf nach Runtime-Freeze steht in `docs/evidence/year-values-browser-independent-2026-11-04/final/independent-30.txt`; keine Fehlschläge, Abbrüche oder übersprungenen Fälle. Die Datei-Hashes vor und nach diesem Lauf waren identisch. Das ist eine begrenzte Browserprüfung und keine Aussage, dass das Gesamtziel, alle steuerlichen Fälle oder die gesamte Software fertig sind.

Der Test verwendet den tatsächlichen `OfficeApi`, die unveränderten Produktmodule und tatsächlich vom Backend erzeugte Antworten/Originalbytes. Netzwerkantworten werden im Node-Test kontrolliert gehalten oder verändert. Der kleine DOM-Harness ist kein echter Browser. Für Hintergrundwechsel wird die tatsächliche `visibilitychange`-Handlerzeile aus `office.js` ausgeführt; der Harness kann dadurch gerade auch Anfangsanfragen ohne offenen Dialog prüfen. Die echten Chromium/MFA/HTTP- und Legacy-EÜR-Läufe gehören dem Browserowner und werden nicht als eigene zusätzliche Fälle gezählt.

## Nachgewiesene und anschließend behobene Befunde

1. **Historische Werte waren in widersprüchlichen Antworten nicht ausreichend an ihre Originale gebunden.** Mit gültiger ursprünglicher Eingabe, unveränderter kanonischer Altpostenfassung und neu berechnetem Vorschauhash wurden ein alter Zahlungstag von August auf September verschoben oder 59,50/50,00 Euro zu 59,51/50,01 Euro geändert. Ein öffentlicher, neu gehashter Quellnachweis konnte außerdem ein Netto-Posting von −49,00 Euro trotz kopierter Originalzeile mit 50,00 Euro enthalten. Der erste tatsächliche Vertragslauf hatte vier Fälle, davon drei rot. Der Owner ergänzt den Abgleich gegen `resolved_sources.record`, tatsächliche Zahlungstage, Netto-/Steuerbeträge, ursprüngliche Journalidentitäten und den Zusammenhang öffentlicher kopierter Zeilen mit den Postings. Dieselben drei Ablehnungsassertionen bestehen jetzt. Der positive Originalfall bleibt lesbar.
2. **Eine gehaltene EÜR-Anfangsanfrage überlebte einen vollständigen Hintergrundzyklus ohne Modal.** Nach Klick auf „Frühere Jahreswerte ausdrücklich übernehmen“ wurde die echte `/accounting/euer/sources`-Antwort gehalten. Der tatsächliche Hosthandler wurde mit hidden→visible ausgeführt, bevor ein Editor existierte. Die freigegebene Erfolgsantwort öffnete erneut private Jahreswerte; die späte 403-Antwort gelangte als Fehler zurück. Der damalige 15er-Lauf hatte genau zwei rote Fälle. Der Owner ergänzt einen dauerhaften privaten Intentzähler, dessen Invalidierung auch ohne Modal erfolgt, sowie eigene `data-year-values-euer`-Marker für Editor, Bestätigung und Pendingansicht. Die ursprünglichen beiden Ergebnisassertionen bestehen jetzt. Neue Folgefälle prüfen außerdem bereits offene Editoren und Bestätigungen.

Die roten Produktkopien, Quellhashes, damaligen Tests und tatsächlichen roten Logs bleiben in `before-original-fix/` und `before-euer-context-fix/` unverändert. Der zusätzlich archivierte frühe `original-red.txt` ist nur ein fehlgeschlagener isolierter Node-Runneraufruf und **kein** Beleg für drei Produktfehler; dafür gilt ausschließlich `contract-red.txt`. Ein späterer neuer Test erwartete zunächst fälschlich die ursprüngliche Transportfehlermeldung statt der beabsichtigten `OfficeApi`-Normalisierung; seine Assertion wurde auf „Keine sichere Antwort“ korrigiert. Auch das war kein Produktbefund.

## Unabhängig abgesicherte Grenzen

- Der tatsächliche Altbeleg hat 119,00 Euro brutto, 100,00 Euro netto und 19,00 Euro Steuer. Die belegte alte Zahlung von 59,50 Euro am 20.08.2026 enthält 50,00 Euro netto und 9,50 Euro bezahlte Vorsteuer. Der bereits früher ausgeübte Vorsteueranspruch von 19,00 Euro bleibt mit seinem ursprünglichen Entstehungszeitpunkt getrennt. Die Jahresquelle erzeugt `cash_movements: []` und keinen neuen Vorsteueranspruch.
- Die Vorschau darf nach Verlust des Schreibrechts oder Abschaltung des Finanzmoduls keine Annahme anbieten. Späte Vorschaufehler nach Dialog-, Sitzungs- oder Hintergrundwechsel dürfen den neuen Inhalt nicht ersetzen. Eine gehaltene zweite asynchrone Vorschau-Hashprüfung darf ebenfalls keine alte Bestätigung öffnen.
- Echte Originalbytes werden auf Länge und SHA-256 geprüft. Der Download eines kanonischen Altpostenoriginals prüft dessen eigene Leserechte nochmals nach den Bytes; erhaltene Jahreswerte-/Finanzrechte ersetzen diese Quellenrechte nicht. Eine späte Dateilesestörung nach Hintergrundwechsel darf weder private Fehlermeldungen zeigen noch einen Upload starten.
- EÜR-Erfolg und 403 nach Hintergrundwechsel oder anderem Dialog dürfen diesen nicht schließen oder dessen Ansicht aktualisieren. Eine tatsächlich gültige Annahme löst ihren ursprünglichen Pendingauftrag intern auf; ein unbestätigter Fehler tut das nicht. Selbst verspätete Autorisierungsfehler vor Beginn beziehungsweise vor Annahme schließen keinen späteren fremden Dialog.
- Zwei gleichzeitig offene Aufträge — Jahresoriginal und EÜR-Übernahme — behalten getrennte ursprüngliche Bodys und Nonces. Die EÜR-Wiederholung nach `clear()` und Hintergrundwechsel erledigt nur ihren eigenen Auftrag; erst die gesonderte Originalquittung erledigt den anderen. Keine neue Vorgangskennung ersetzt einen unbestätigten Auftrag.
- Eine tatsächliche nachträglich unvollständige Profilantwort bleibt für vorhandene historische Werte, Originale und Historie lesbar. Sie erlaubt keinen neuen Vortragsentwurf und erfindet keinen Buchführungsbeginn. Die Anzeige behauptet aus vollständiger erklärter Vorperiode keine Vollständigkeit des gesamten Unternehmensjahres.

## Originale und Dateien

Die ursprüngliche Backendfixture `docs/fixtures/accounting_year_values_v1.json` bleibt unverändert: SHA-256 `441f0665a27dd304f229dbf604c09f5463013c636c222c47cf8f581e3b7eb5d5`.

Die separate echte EÜR-Companionfixture `web/office/tests/fixtures/accounting-year-values-euer-ui.json` enthält den tatsächlich passenden Journal-/Report-/Kontenstand vor der EÜR-Übernahme sowie die echten kanonischen Originalbytes: SHA-256 `a3fd1e91e6e913b965693efe1eff69c55c42b26a5ee082720aedea6051a0926a`. Sie ersetzt oder verändert die ursprüngliche Fixture nicht.

Eigene dauerhafte Testdateien:

- `web/office/tests/accounting-year-values-independent.test.mjs`
- `web/office/tests/accounting-year-values-independent-lifecycle.test.mjs`
- `web/office/tests/accounting-year-values-independent-harness.mjs`

Das maschinenlesbare Manifest neben dieser Evidenz bindet Produktstand, Fixtures, eigene Tests, rote Originalbelege und abschließendes Laufprotokoll. Es gilt nur für diese Hashes. Produktkorrekturen stammen vom Browserowner; Änderungen an `office.js` und `accounting-euer.js` müssen bei Integration die übrigen bestehenden Verträge und Guards erhalten.
