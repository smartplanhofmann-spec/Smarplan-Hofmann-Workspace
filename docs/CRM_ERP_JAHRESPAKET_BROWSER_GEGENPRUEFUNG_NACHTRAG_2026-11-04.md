# Jahrespaket-Gegenprüfung: neuer Archivstand und Vertrauensgrenze

Separater Nachtrag vom 04.11.2026 zum unveränderten [ursprünglichen Browserreview](CRM_ERP_JAHRESPAKET_BROWSER_GEGENPRUEFUNG_2026-11-04.md). Dessen Manifest `c4c6b8b9c12c9b76550152689909960341b27569de828e9487f235fdcd38f671` und alle 18 eigenen Artefakte wurden erneut auf Unverändertheit geprüft. Keine Produktdatei wurde durch den Reviewer geändert.

## Neuer tatsächlich erzeugter Archivstand

Die beiden vom Backendowner ausdrücklich eingefrorenen Dateien `docs/fixtures/accounting_year_package_v1.json` und `app/test/fixtures/accounting_year_package_v1.json` sind bytegleich: **719679 Bytes**, SHA256 **`a859f2bbbcfab6f890c2968a05aa2fa839299117ae43b8e15e2d7852c82d36a0`**. Sie enthalten dieselben sechs Szenarioarten in frisch erzeugten tatsächlichen Testinstanzen; ihre IDs sind deshalb nicht als identische alte Instanz behauptet. Die HTTP-Metadaten behalten ihre 16 Felder.

**Alle sechs neuen Archive bestehen die unabhängige Inhaltsprüfung.** Geprüft sind Gesamthash und Größe gegen die separat gelieferte Metadatenantwort, jedes ZIP-Mitglied, jeder Originalhash und dessen Byteanzahl, feste Dateireihenfolge/ZIP-Merkmale, ursprüngliches Report-JSON, bytegleiches CSV sowie die unveränderte Bedeutung von Jahresvollständigkeit und privaten Personalgrenzen. Innerhalb der neuen Fixture bleibt das archivierte normale Jahr nach späterer Profiländerung bytegleich.

Zusätzlich läuft der vertrauenswürdige aktuelle Prüfer aus dem Repository mit `metadata.sha256` als externem Anker gegen jedes Archiv. Sein Quelltext stimmt bytegleich mit dem jeweils mitgelieferten `verify_year_package.py` überein; ausgeführt wird die Repositorydatei, kein aus dem ZIP extrahiertes Programm. Alle sechs Ergebnisse enthalten ausdrücklich:

```json
{"verified": true, "intrinsic_dependency_closure": false, "verification_basis": "separately_authenticated_archive_sha256_and_structural_checks"}
```

**18 negative Varianten werden abgewiesen:** je Archiv fehlender externer Hash, falscher externer Hash und veränderte Archivbytes bei unverändertem authentisiertem Anker. Der Anker wird nicht aus dem Archivmanifest abgeleitet. Manifest und Prüfer benennen `required_trust=separately_authenticated_archive_sha256` und `intrinsic_dependency_closure=false`.

Diese Grenze ist wesentlich: Interne Konsistenz und passender Dateihash sind keine Signatur und kein eigenständiger Beweis, dass alle ursprünglich benötigten Belege und Abhängigkeiten enthalten sind. V1 benötigt den separat authentisierten, außerhalb der ZIP aufbewahrten Hash. Der Browserowner hat den sichtbaren Hinweis entsprechend präzisiert. Ein unvollständiges Jahr bleibt unvollständig; öffentliche Lohn-/Reisekostenprojektionen behaupten keine privaten Personaloriginale. Eine technische erfolgreiche Prüfung ist weiterhin keine steuerliche Fachfreigabe oder DATEV-Zertifizierung.

## Enger Clientnachlauf

Die 21 eigenen und 28 Owner-Jahrespaketfälle wurden mit der neuen Hauptfixture und dem präzisierten UI-Text wiederholt: **49/49 bestanden**. Die eingefrorene eigene Zweiexportfixture bleibt als historischer Teststand unverändert. Vertragsreader, bestehender EÜR-Exportkontext und tatsächlicher Office-Hintergrundhook sind bytegleich zum zuerst geprüften reparierten Stand. Die einzige geänderte Datei dieser vier Produktdateien ist die Jahrespaketansicht mit dem ergänzten Vertrauenshinweis. Der Browserowner führt seinen tatsächlichen neuen ZIP-/HTTP-Nachlauf separat durch; dieser Nachtrag zählt keinen fremden Ablauf als eigenen tatsächlichen Browserlauf.

## Präzisierung des früheren Hash-Zeitpunkts

Das ursprüngliche rote Protokoll mit drei tatsächlich fehlgeschlagenen Exportkontextfällen stammt von **11:48:04 UTC**. Der Owner schrieb die beiden korrigierten Runtime-Dateien um **11:49:32 UTC**. Die Datei mit dem Namen `before-hashes.json` entstand erst um **11:49:33 UTC** und enthält damit bei `accounting-euer.js` und `office.js` bereits die Hashes des reparierten Stands. Sie darf entgegen dem Dateinamen und der ungenauen Formulierung im ursprünglichen Bericht nicht als historischer Runtime-Snapshot vor dem Fix verstanden werden. Die ursprünglichen Artefakte bleiben nachvollziehbar unverändert; dieser Nachtrag stellt die zeitliche Aussage richtig.

Zur zusätzlichen kausalen Absicherung wurde ausschließlich in einer temporären Kopie der aktuelle Exportabsichts-/Hintergrundzähler gezielt entfernt. Mit unveränderten Ergebnisassertionen schlagen genau dieselben drei Fälle fehl, die übrigen 18 eigenen Fälle bestehen. Diese kontrollierte Negativprobe ist ausdrücklich **kein behaupteter historischer Quellstand**. Im tatsächlichen unveränderten Produktstand bestehen alle 49 Fälle.

## Wiederholung

```sh
/tmp/smartplan-backend-verified/bin/python web/office/tests/accounting-year-package-independent-archive-addendum.py
node --test --test-isolation=none web/office/tests/accounting-year-package-independent.test.mjs web/office/tests/accounting-year-package.test.mjs
/tmp/smartplan-backend-verified/bin/python docs/evidence/year-package-browser-independent-addendum-2026-11-04/reproduce-context-guard-removal.py
```

[Eigenes Nachtragsmanifest](evidence/year-package-browser-independent-addendum-2026-11-04/manifest.json) mit Quellen-/Artefakthashes und genauen Resultaten. Kein Extrahieren der Archive, kein Datenbank-/Netzzugriff durch die Archivprüfung, keine Produktänderungen, Commits oder Stagingänderungen.
