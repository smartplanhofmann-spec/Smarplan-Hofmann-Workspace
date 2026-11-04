# Eigener CSV-v2-Katalog: ausgeführte Nachweise

Arbeitsbaum: `/workspace/smartplan-catalog-prices-v2-20261104`, 4. November 2026. Ausschließlich synthetische lokale Quellen, Kunden, Bestellungen und Dateien; keine Lieferantenverbindung. Die exakten Dateihashes stehen in `package-files.json` und den beiden Komponenten-Handoffs. Dies ist ein abgegrenzter Katalogbaustein, keine Fertigmeldung für das Gesamtziel.

## Durchgeführte Prüfungen

| Nachweis | Tatsächliches Ergebnis und Grenze |
|---|---|
| `backend-regression-before-final-review.txt` | 1.608 Backendtests, ein plattformbedingter Skip, sonst grün. Dieser Lauf begann vor den späteren engen Originalartikel-/Positionskorrekturen; er wird nicht als Prüfung des letzten Gesamtstands ausgegeben. |
| `backend-targeted-final.txt` | 57/57 gezielte Fälle im letzten eingefrorenen Backendstand (45 Domain-/Consumer-/Einkaufs-/Integritätsfälle plus zwölf unabhängige Reviewtests), alle grün. |
| `backend-targeted-before-independent-review.txt` | 42 gezielte Domain-/Consumer-/Einkaufs-/Integritätsfälle vor den unabhängigen historischen Identitätskorrekturen. |
| `../catalog-independent-review-2026-11-04/` | Unabhängig: zwölf eigene Gegenfälle und insgesamt 103 Tests grün nach den gezielten Dokument-/Stücklistenkorrekturen; drei frühere rote Reproduktionen und echte wiederhergestellte SQL-Guards dokumentiert. |
| `purchase-original-identity-before.txt`, `purchase-original-identity-after.txt` | Eigener zusätzlicher Bestellbefund: ein Test mit drei roten Unterfällen (nicht vorhandene ursprüngliche Revision, veränderter Name, veränderter Kostenwert); nach Fix 66 Einkaufs-/Lager-/unabhängige Reviewtests grün. Zweiter positiver Fall erhält eine alte Bestellung trotz Änderung des heutigen Artikels. |
| `postgresql-three-before-identity-review.txt` | Drei echte PostgreSQL-Fälle: MFA/HTTP einschließlich 2 MiB, unabhängige konkurrierende Runtimeverbindungen sowie tatsächlicher Dump/Restore mit gebundenem Novemberangebot und Originalbytes. Vor den letzten historischen Identitätskorrekturen ausgeführt; keine PostgreSQL-Migration wurde danach verändert. Root prüft die gemeinsame Integration gesondert. |
| `http-transport-final.txt` | Drei gezielte echte lokale HTTP-Fälle im letzten Backendstand: 2-MiB-Originale, 1.000 Unicode-Bindungsentscheidungen oberhalb 1 MiB und strikte Größen-/Framinggrenzen; alle grün. |
| `source-reference-domain-final.txt` | 15 Domainfälle grün; zwei namensgleiche Quellen bleiben anhand ihrer belegten Referenzen unterscheidbar, bestehende Snapshot-Hashes unverändert. |
| `../catalog-prices-native-2026-11-04-handoff.json` | Native Owner: 70 neue Fälle, kombinierter Bestand 182/182 grün, Analyse von 14 Dateien0. Tatsächlicher HTTP-Test mit 2 MiB / 2.000 Preiszeilen und exakten Antwortgrenzen eingeschlossen. |
| `../catalog-native-independent-2026-11-04/` | Unabhängiger Nativeabschluss: 87/87 grün (17 eigene Lifecyclefälle plus 70 gezielte Ownerfälle), neue Reviewdatei Analyse 0. Backend-Purchasing-Nachtrag zusätzlich 17/17 unabhängig grün. Alle geprüften Runtime-/Ownertest-/Fixturehashes entsprechen unverändert dem Handoff. |
| `packages-sixteen.txt` | 16 Paket-/Exports-/Registrierungsprüfungen grün. |
| `browser-targeted-final.txt` | 32 gezielte Nodefälle, einschließlich verlorener Antworten und frischer Projektberechtigung für datierte Verbraucher; alle grün. |
| `node-regression-final.txt` | Vollständige Node-Regressionssuite: 554/554 grün, mit `--test-isolation=none` als tatsächlichen Einzelfällen gezählt. |
| `browser-late-document-before.txt`, `browser-picker-background-before.txt`, `browser-lifecycle-addendum.json` | Zusätzliche belegte rote Fälle: spät angenommene Belegantwort schloss einen späteren Dialog; Hintergrund ließ bereits kopierte private Preisfelder im Elterneditor. Eng datierter Rückweg plus eigener sichtbarer Picker schließen die Lücken. Zwei positive Gegenfälle halten Legacy- und nachfolgende unabhängige Dialoge offen. Vorher-/Nachherhashes und enger Diff liegen bei. |
| `chromium-http-final.txt`, `catalog-v2-evidence.json`, Screenshots | Tatsächlicher Chromium-/MFA-/HTTP-Ablauf, aktivierter Namespace-/PID-/Network-/Seccomp-Sandbox. Datei, Originalhashdownload, explizite Artikelbindung, getrennte Korrekturbestätigung, identische Upload-/Annahme-Replays, November-/Dezembergrenze, unverändertes altes Angebot, Bestellvorschlag/Freigabe und ausdrücklich belegter Bestelltag. |
| `chromium-invoice-chain-regression.txt` | Bestehende echte Rechnungskette nach der Browserpositionsänderung weiterhin grün. |

Die Screenshots zeigen die tatsächlich geöffnete Preisübernahme auf Desktop und bei 390 Pixeln. Die JSON-Datei enthält synthetische Fachquittungen, keine Anmeldedaten.

## Verwendete Ausführung

Python: `/tmp/smartplan-backend-verified/bin/python`, `PYTHONPATH=backend:backend/business_tests:backend/online:scripts`. Vollprüfung: `python -m unittest discover -s backend -p 'test_*.py'`. Der unabhängige Prüfer hat seinen eigenen Befehl und seine eigenen Quellhashes im separaten Verzeichnis festgehalten.

Browser: `node --test --test-isolation=none web/office/tests/*.test.mjs`. Der tatsächliche Ablauf nutzt `SMARTPLAN_BROWSER_WORKFLOW=catalog-prices`, `SMARTPLAN_BROWSER_TEST_PYTHON=/tmp/smartplan-backend-verified/bin/python`, `SMARTPLAN_CHROMIUM_BINARY=/usr/lib/chromium/chromium`, `SMARTPLAN_BROWSER_NAMESPACE_SANDBOX=1` und `node web/office/tests/e2e.cjs`. Backend läuft nur als lokaler synthetischer Testserver; MFA wird im tatsächlichen Browser durchlaufen.

Die PostgreSQL-Fixture ist auf Loopback und eine ausdrücklich begrenzte Testdatenbank beschränkt. Der Restore bricht bei bereits vorhandenem Ziel ab. Zugangswerte werden nicht archiviert. Der Cluster wurde nach dem Lauf für Root freigegeben.

## Integrationsgrenze

Der Arbeitsbaum hat einen bereits geänderten Ausgangsstand. `git diff HEAD` allein ist deshalb kein V2-Diff. `catalog-prices-v2-baseline.json` dokumentiert die 1.626 ursprünglichen Dateihashes. Für fünf native V1-Dateien gilt zusätzlich der überprüfte Import aus Root-Commit `4c2f0086b4a9979b7cbe9d261fc22a97cd046913`; dessen Einzelhashes stehen in `catalog-prices-v2-native-v1-baseline.json`. Neue V2-Änderungen werden gegen diese passende Basis ausgewiesen.

Root führt Registry, Schema, HTTP-Grenzen, Export-/Paketlisten, Browser-Import, `OfficeApi`, statische Allowlist und CI mit seinen neueren Source5-/Anlagenänderungen zusammen. Vorhandene Original-/V1-Tabellen und Quittungen werden nicht umgeschrieben. Der abschließende gemeinsame Rootlauf bleibt gesondert erforderlich.
