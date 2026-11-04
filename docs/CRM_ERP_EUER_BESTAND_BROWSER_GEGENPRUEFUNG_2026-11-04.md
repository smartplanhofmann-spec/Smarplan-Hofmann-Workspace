# Zusätzliche unabhängige Browserprüfung des bestehenden EÜR-Geldflusswegs

Stand: 04.11.2026, isolierter Arbeitsbaum `/workspace/smartplan-opening-items-20261104`. Dieser Nachtrag ist getrennt von der bereits abgegebenen Altpostengegenprüfung. Deren Manifest bleibt bytegleich bei `7a1836612f366c88ce911b88b74f47732eba154934f938734b4bb864bcc0ea3d`.

## Tatsächlicher Bestandsfall

Der eigene Generator `web/office/tests/accounting-euer-legacy-context-fixture.py` verwendet den bestehenden `EuerWorkflowTests` mit echter temporärer SQLite-Datenbank, `sale()`, `cash_payload()`, aktuellem EÜR-Zustand, ursprünglicher Quellenliste, Vorschau und Annahme. Nur das bereits vorhandene synthetische Rechnungsarchiv des Bestandsfixtures dient als Belegursprung. Keine Fachfunktion wird ersetzt.

Die gespeicherte Fixture `web/office/tests/fixtures/accounting-euer-legacy-context.json` besitzt SHA-256 `5f46a17678fbffb114edc9ab855eec73fd9e4c7bf78c43c4ed60d7237a5b3a70`. Operation ausschließlich `cash`: tatsächlicher Zufluss `119,00`, bestätigte EÜR-Buchungen Erlös `100,00` und vereinnahmte Umsatzsteuer `19,00`, dazu Ist-Umsatzsteuer `19,00`. Der Generator prüft auch die exakte erneute Annahme desselben ursprünglichen Backendbefehls. Das ist kein Altpostenimport.

Der neue unabhängige Node-Test `web/office/tests/accounting-euer-legacy-context.test.mjs` verwendet ausschließlich die bisherigen `accounting_euer`-Capabilities; `accounting_open_items` ist nicht registriert. Er verarbeitet die tatsächlichen Quellen, den unveränderten echten Vorschau-Body und die echte Quittung. Erfundene wirtschaftliche Antwortprojektionen werden dafür nicht benötigt. Ein positiver normaler Ablauf belegt, dass die Teststeuerung gültige Vorgänge zulässt.

## Reproduzierter Befund vor der Korrektur

Der erste Lauf zeigte **1 positiven Fall grün und 8 Gegenfälle rot**:

- Gehaltene ursprüngliche Quellenantwort oder Vorschau öffnet nach dem Wechsel in einen fremden Dialog wieder private Buchungsdaten.
- Gehaltene gültige Bestätigungsantwort schließt den inzwischen neu geöffneten fremden Dialog und aktualisiert die Oberfläche.
- Verspätete Rechteverweigerung während Initialabruf, Vorschau oder Bestätigung schließt über `onDenied` einen neueren Dialog.
- Während des Quellenabrufs tatsächlich entzogenes Finanzleserecht wird vor Anzeige des Editors nicht frisch geprüft.
- Eine gültige Wiederholungsquittung des ursprünglichen offenen `cash`-Auftrags schließt nach Dialogwechsel die neuere Ansicht.

Die drei ersten Erfolgspfade sind getrennte Gegenfälle, ebenso die drei Rechtefehler. Die Behauptung beruht auf tatsächlichen roten Prüfungen mit dem ursprünglichen Bestandsvertrag, nicht auf einer bloßen Übertragung des Altpostenbefunds. Die roten Logs und die zugehörigen Datei-/Fixturehashes liegen in `docs/evidence/euer-legacy-browser-context-2026-11-04/`.

Der Reviewer ändert ausschließlich seine neue Test-/Fixture-/Nachweisdateien. Die gezielte Produktkorrektur im bestehenden EÜR-Client liegt ausschließlich beim Browserowner; der folgende Abschlussnachweis prüft diesen Fix unabhängig. Keine Produktivkontakte, kein eigener MFA-/Chromium-Nachweis und keine Gesamtfreigabe.

## Gezielte Korrektur und abschließende Nachprüfung

Der Browserowner erweiterte den vorhandenen privaten Kontextschutz genau auf den nachgewiesenen bestehenden `cash`-Vorgang und dessen belegte Korrektur/Gegenbuchung. Weder ein neues Altpostenfeature noch eine andere Quellenart wird dafür automatisch registriert. Späte Erfolge und Fehler verändern keine fremde Ansicht; nach gehaltenen Quellenantworten werden die aktuellen Rechte erneut geprüft.

Die ergänzende echte Fixture `accounting-euer-legacy-followups.json` wurde mit demselben Generator und `--followups` erzeugt. Sie enthält eine tatsächlich angenommene Korrektur derselben Cashquelle und deren anschließende echte Gegenbuchung. Für diese Gegenbuchung ist `preview.effect` tatsächlich `null`; ihr ursprünglicher Body enthält nur `entry_id`. Eine verlorene Antwort darf deshalb nicht durch eine erfundene Quelle oder ein ergänztes Bodyfeld ersetzt werden.

Der bestehende Client merkt sich dafür nur die zur ursprünglichen offenen Nonce bereits bekannte Schutzzuordnung in derselben Sitzungsgeneration. `clear()` entfernt sichtbare Bestätigung, Quelldaten und Entwürfe, erhält aber den Kontextschutz der weiter offenen ursprünglichen Operation. Bei Sitzungswechsel wird auch diese Markierung verworfen. Die Tests prüfen beide tatsächlich angenommenen Folgefälle normal, mit gehaltener Vorschau und mit exakter Pendingwiederholung nach `clear()` und neuem fremden Dialog. Gültige ursprüngliche Quittungen lösen den offenen Auftrag intern auf; ihre späte Antwort darf weder fremde Dialoge schließen noch einen Refresh starten.

**Ergebnis: 15/15 neue Legacyfälle grün**, darunter die acht zuvor roten Varianten. Zusammen mit den unveränderten 30 unabhängigen Altpostenfällen sowie vorhandenen Altposten-/EÜR-/Banktests: **88/88 grün**. Die früheren eigenen Altpostentest-/Fixture-/Nachweisdateien wurden zusätzlich byteweise gegen ihr eingefrorenes Manifest geprüft: keine Abweichung. Der Owner führt danach seine vollständige Browser-/HTTP-Integration aus.

Abgabe: eigene neue Legacy-Testdatei, Generator, zwei tatsächliche Fixturedateien, dieser Bericht und separater Evidenzordner. Das neue Manifest enthält die final geprüften Runtimehashes als nur gelesene Abhängigkeiten; Produktänderungen bleiben ausschließlich beim Browserowner. Die ursprüngliche Altpostenabgabe dokumentiert ihren früheren Prüfzeitpunkt und wird nicht rückwirkend umgeschrieben.
