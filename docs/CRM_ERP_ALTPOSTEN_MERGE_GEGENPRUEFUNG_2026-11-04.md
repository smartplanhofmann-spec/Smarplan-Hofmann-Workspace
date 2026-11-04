# Unabhängige Merge-Gegenprüfung der Altposten · 04.11.2026

Geprüfter Arbeitsbaum: `/workspace/smartplan-opening-items-integration-20261104`; bestehende Hauptbasis `13af5bc1147170948c5de8fa9f831a7215974cb5` mit Ereignissen, Source5, historischen Anlagen und datierten Katalogpreisen. Der eingehende Altpostenstand beruht auf `80e051a28ad6ffe2b25818ed26d198f49ebb0c09` und sieben unveränderten Owner-/Reviewmanifesten. Dies ist eine gezielte Integrationsgegenprüfung; sie beansprucht keine Vollprüfung der Gesamtsoftware oder steuerliche Fachfreigabe.

**Kein bestätigter offener Merge-Befund.** Der Reviewer hat keine Produktdateien geändert. Alle **193** gebundenen Dateien stimmen mit dem dokumentierten aufgelösten Stand überein, **180** davon direkt mit dem jeweiligen letzten Ownerhash. Die übrigen 13 bestehen aus zehn ausdrücklich aufgelösten Konfliktdateien und drei automatisch zusammengeführten Dateien. Alle sieben Originalmanifeste sind bytegleich. Die 142 neuen Dateien und 38 sauberen Ersetzungen wurden ebenfalls vollständig per SHA256 verglichen.

## Erhaltene Schutzprüfungen

Die native `BusinessSession` enthält sämtliche 3246 bisherigen Zeilen in derselben Reihenfolge; hinzu kommen 97 Zeilen, keine wurde gelöscht. Die Ergänzung ist auf Altpostenoriginale und deren bestätigte Annahme begrenzt und verwendet den vorhandenen Workflow-Replay mit aktuellen globalen Rechten, Finanzmodul, Funktionsstand und ursprünglichem Auftrag. Source5, Ereignisse, datierte Verbraucher und der bereits vorhandene Schutz paralleler Antworten bleiben erhalten.

Die gesamte Browserklasse `OfficeApi` ist nach Entfernen exakt zweier additiver Altpostenhooks bytegleich mit der Hauptbasis: Ein frischer Altposten-Rechtecheck vor Wiederholung und der Schutz unklarer Altpostenantworten kamen hinzu. Originalbody/-nonce, ursprünglicher Validator, isolierte Bodykopie und die Sitzungs-/Operationsprüfung vor und nach dem asynchronen Validator wurden nicht ersetzt. Die vorhandenen Gates für Events, V2-Katalogverbraucher, Source5 und Anlagen bleiben identisch.

Der tatsächliche globale Ereignis-Hintergrundschutz bleibt auch ohne offenen Dialog wirksam: `companyEvents.clear()` läuft weiterhin bei `document.hidden`. Hinzu kommt nur das parallele Leeren der Altpostenansicht sowie deren Modalmarker. Der zuvor unabhängig belegte falsche Erfolgsstatus bleibt gesperrt: `succeeded` erfordert eine tatsächliche Ausführung mit `outcome.status === succeeded`; gültige historische stale-/suspended-Ansichten mit früherem Ergebnis bleiben lesbar. Die Ereignismodule selbst sind bytegleich zur Hauptbasis. Die vorhandenen Modal-Keep-Schalter für die privaten Lohnbereiche und Events bleiben beim zusätzlichen Altpostenschalter erhalten.

23 ausdrücklich ausgewählte Produktdateien für Events, Source5, V2, gemeinsame API und SharedEditor wurden zusätzlich bytegleich gegen die Hauptbasis geprüft. Die neu übernommenen Altposten- und EÜR-Dateien stimmen mit den finalen Owner-/Reviewfix-Hashes überein, einschließlich tatsächlichem Geldkonto, historischem Item-/VAT-Bezug, Quittungsbindung und ursprünglichem Cash-Pending-Scope.

## Registrierung, Transport und Restore

API- und Schemaregistrierung bewahren alle alten Module in identischer Reihenfolge; nur `business_accounting_open_items` kam hinzu. Beide HTTP-Implementierungen sind nach Entfernung des exakt neuen Originaluploadpfads und der zwei neuen Browsermodule bytegleich zur Hauptbasis. Die bisherigen engen 1-MB-/2,85-MB-/7,1-MB-Entscheidungen und V2-Pfade bleiben erhalten. Für den Altpostenoriginalupload gilt der bestehende große Envelopepfad. Die native 32-MiB-Katalogantwort-Whitelist ist bytegleich; eine generelle Anhebung fand nicht statt.

In `business_schema.py` sind 42 von 45 bestehenden Funktionen AST-identisch. Die drei fachlich erforderlichen Erweiterungen betreffen den Finanzhorizont, dessen Validator und den expliziten Restoreabgleich. Der neue Horizont 14 mit `opening_items` verlangt Bericht 15. Entfernt man ausschließlich den neuen Bericht-15-Zweig, ist der alte Validator AST-identisch. Alte Horizont-13-/Bericht-14-Quittungen werden nicht umgeschrieben; eine neue Freigabe des erweiterten installierten Scopes darf keinen alten unvollständigen Bericht verwenden. Diese Unterscheidung wurde zusätzlich mit vier tatsächlich ausgeführten Registrierungs-/SQLite-Fällen geprüft.

Die Paketlisten enthalten **137 Backenddateien statt 134** und **159 Operatordateien statt 150**. Es fehlen keine bisherigen Einträge, keine Quelle und keine neue referenzierte Datei; Duplikate sind ausgeschlossen. Nativepaket, Windows-Supportpaket und Windows-CI enthalten identische Listen. Die Browser-CI behält Events, Katalog und alte Abläufe und ergänzt den tatsächlichen Altpostenablauf.

Außerhalb der 193 eingehenden Dateien existieren keine unerklärten Produktänderungen. Die drei zusätzlichen Codepfade sind ausdrücklich beauftragte PG-Tests: zwei bestehende Gesamtrestoretests wurden auf den jetzt tatsächlich installierten Horizont 14/Bericht 15 angepasst; der dritte prüft befüllt Altposten plus Source5, V1-/V2-Originale, Anlagen, EÜR und Events. Dessen Quelltext prüft unveränderte Originalbytes, Angebotspreissnapshot, Lohn-PDF, EÜR-Export und Nonce-Replays nach Restore sowie das fortbestehende Aussetzen einer noch nicht ausgeführten Ereignisfreigabe. Im tatsächlichen erwarteten EÜR-Fall ergeben 1200,00 EUR Anlagenfortführung und 119,00 EUR spätere Altverbindlichkeitszahlung 1319,00 EUR Ausgaben bei **0,00 EUR neuem Vorsteuerabzug**. Dieser Reviewer hat den PG-Lauf nicht doppelt gestartet; dessen Ausführung liegt beim Integrator.

## Eigene Wiederholung im zusammengeführten Baum

- **96/96 Nodefälle**: eigene frühere Altposten-/Legacy-Cash-Gegenfälle sowie vorhandene Ereignis-Vertrag-/Kontext-/Quittungstests, ursprünglicher falscher Erfolg und V2-Lifecycle.
- **4/4 tatsächliche Registrierungsfälle**: vollständiger neuer Scope, unzulässige fehlende/zusätzliche/boolsche/negative Angaben, alte angenommene Bericht-14-Quittung nach additiver Installation unverändert, Originalbytes im Export, explizite Routen sowie gesperrter Offline-/Modulpfad.
- **16/16 Paketprüfungen** mit tatsächlichen temporären Quell-/Supportarchiven.

```sh
python docs/evidence/opening-items-merge-independent-2026-11-04/audit.py
node --test --test-isolation=none web/office/tests/accounting-open-items-independent.test.mjs web/office/tests/accounting-euer-legacy-context.test.mjs web/office/tests/company-events-contract.test.mjs web/office/tests/company-events-session.test.mjs web/office/tests/company-events-access.test.mjs web/office/tests/company-events-independent-review.test.mjs web/office/tests/company-events-merge-review.test.mjs web/office/tests/catalog-prices-lifecycle.test.mjs
# Im Backendverzeichnis:
/tmp/smartplan-backend-verified/bin/python -m unittest test_accounting_open_items_registration -v
# Im Projektverzeichnis:
/tmp/smartplan-backend-verified/bin/python -m unittest discover -s scripts -p test_native_release.py -v
```

Das [Evidenzmanifest](evidence/opening-items-merge-independent-2026-11-04/manifest.json) bindet den lesenden Audit, alle 193 Vergleichsresultate, sieben Originalmanifeste, Konfliktprotokolle, geprüfte Diffs und eigene Testausgaben. Der laufende vollständige Backend-/Flutter-/PG-Nachweis des Integrators ist nicht als eigene Leistung eingerechnet. Keine Commits, kein Staging und keine Produktivkontakte.
