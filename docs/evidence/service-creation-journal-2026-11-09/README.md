# Service-Anlagejournal – Prüfnachweise

Ausgangsstand: `a7c1e0b` in einer getrennten Arbeitskopie. Produktiver Backendcode und Datenbankschema sind unverändert. Alle HTTP-Daten stammen aus kurzlebigen synthetischen Firmen; keine externen Dienste wurden verwendet.

## Nachgewiesener Ausgangsfehler

`original-duplicate-probe.dart.txt` und `original-duplicate-probe.log` sind unveränderte Kopien des unabhängigen Gegenbeweises. Eine angenommene manuelle Fallanlage verliert ihre Antwort. Nach Neuerstellung der Sitzung erzeugt dieselbe Eingabe eine zweite Request-ID und einen zweiten persistenten Fall. Das grüne Ergebnis dieses Negativtests bestätigt den Fehler im Ausgangsstand, nicht den korrigierten Ablauf.

## Prüfungen des Kandidaten

- `journal-unit.log`: 19 gezielte Fälle bestanden. Echter AES-GCM-Dateispeicher, SecureStorage-Mock, unveränderte Unicode-Eingaben, getrennte Konten/Server/API-Versionen, fremde Firma vor Zugriff auf den offenen Inhalt gesperrt, Versionsvergleich gegen konkurrierende Schreibvorgänge, fehlende Schlüssel, beschädigte/neuartige Speicherzustände, Schreibfehler und späte Kontextwechsel.
- `http-ui-pass.log`: fünf Fälle bestanden. Drei nutzen echte lokale HTTP-Verbindungen zum Produktserver; zwei prüfen die optionale Dropdownauswahl. App, Sitzung und API werden neu erstellt; der Gerätespeicher bleibt erhalten. Der explizite Retry verwendet exakt den ursprünglichen Befehl. Datenbankabnahme: ein Fall, eine Anfangsversion, ein Erstellungsereignis.
- `regression-before-title-assert-fix.log.json`: 45 bestehende Service-, Editor- und Lifecyclefälle und die zwei übrigen neuen HTTP-Fälle bestanden. Der Gesamtlauf war wegen eines falschen Vergleichs des neuen Widgettests noch rot: Er verglich den unveränderten Titel mit abschließendem Leerzeichen gegen den dokumentiert getrimmten Servertitel. Der spätere grüne HTTP/UI-Lauf prüft die korrekte Darstellung; die ursprüngliche Fehlermeldung bleibt erhalten.

`candidate.log` bestätigt den abschließenden gemeinsamen Satz: **24/24 bestanden** in 38 Sekunden (19 Journal-, drei tatsächliche HTTP-/App-Neuerstellungsfälle und zwei Leeroptionsfälle). `analyze.log` enthält die fehlerfreie statische Analyse aller geänderten Dartdateien. `service-create-recovery-390.png` zeigt synthetische wiederhergestellte Eingaben vor dem erneuten Senden bei 390 Pixeln Breite.

`existing-regressions.log` bestätigt anschließend **45/45 bestehende Service-, Editor- und Lifecyclefälle** in 31 Sekunden ohne Fehler. Die Protokolle und die Vorschau sind mit `SHA256SUMS` prüfbar.

## Bewahrte Fehlversuche

Die fehlgeschlagenen Logs sind als JSON-Strings gespeichert. JSON-Dekodierung stellt ihre ursprünglichen Bytes einschließlich abschließender Leerzeichen unverändert wieder her; die Originalprüfsummen stehen in `decoded-log-sha256.json`. So bleiben die Fehlermeldungen erhalten, ohne Quellen-Whitespace-Prüfungen zu verfälschen.

`http-initial.log.json`, `http-scope-initial.log.json` und `http-before-ui-fixes.log.json` dokumentieren die anfängliche unvollständige Testbereitschaft und den zuerst unpassenden TestDevice-Öffner. Der Widgettest wartete zunächst nur auf einen sichtbaren Anlagebutton, obwohl die Seite noch HTTP-Daten lud. Er wartet jetzt auf das tatsächliche Ende der Seitenladung und treibt Flutter-Zeit während der echten I/O voran. Keine Zeitüberschreitung wurde erhöht.

`ui-before-dropdown-fixes.log.json` zeigt die danach erreichten tatsächlichen Produktfehler: überlaufende Servicefilter bei 390 Pixeln und ein doppelt vorhandener leerer Auswahlwert im wiederhergestellten Formular. Beide Fehler wurden eng korrigiert; die zwei Varianten mit vorgegebener beziehungsweise automatisch ergänzter Leeroption sind gesondert geprüft.

## Wiederholung und Grenzen

Aus `app/` mit den installierten Flutter- und Python-Abhängigkeiten:

```sh
SMARTPLAN_TEST_PYTHON=/path/to/backend/python flutter test --no-pub test/service_creation_journal_test.dart test/service_creation_journal_http_test.dart test/business_editor_empty_choice_test.dart --concurrency 2 --reporter expanded
flutter test --no-pub test/business_service_test.dart test/business_editor_context_test.dart test/business_service_equipment_lifecycle_review_test.dart --concurrency 2 --reporter expanded
```

`SMARTPLAN_CAPTURE_UI=1` und `SMARTPLAN_UI_OUTPUT=/path/to/output` sichern die mobile Vorschau. Der HTTP-Test ist wegen des realen lokalen Pythonservers als `posix_backend` markiert und wird vom vorhandenen Linux-CI-App-Test aufgenommen. Die Journal- und Leeroptionstests benötigen keine POSIX-Ausnahme.

Hier wurde Linux geprüft. Eine echte Windows-/Mobilinstallation und der jeweilige Betriebssystem-Schlüsselspeicher wurden nicht ausgeführt. Es erfolgten kein Push und keine Serverinstallation.
