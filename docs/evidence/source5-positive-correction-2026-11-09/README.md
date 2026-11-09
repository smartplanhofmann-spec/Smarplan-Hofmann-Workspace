# Gemeinsamer Source5-Korrekturstand, 09.11.2026

Die ursprünglichen Backend-Teilnachweise in `verification.json` bleiben
unverändert. Die spätere gemeinsame Integration umfasst Browser, native App,
tatsächliche PostgreSQL-/HTTP-/MFA-Prüfungen sowie Jahres-/EÜR-/Restorewege.

## Gemeinsame Prüfläufe

| Prüfung | Ergebnis | Unveränderte Rohquelle |
| --- | --- | --- |
| Neue tatsächliche PostgreSQL-Fälle | 4 bestanden, 574,197 s, kein Skip | `postgres-initial-four.gz` |
| Finaler PostgreSQL-Jahres-/Mitarbeiter-/Restorefall | 1 bestanden, 452,420 s, kein Skip; überlappt den ersten Fall oben | `postgres-annual-final.gz` |
| Reale Source5-Browserfolge | zweimal bestanden; echte MFA, Originalquellen, zwei verlorene Antworten und Mobilansicht | `browser-e2e-initial.gz`, `browser-e2e-final.gz` |
| Browsermodulprüfungen nach Jahresverbraucher-Ergänzung | 902 bestanden, kein Skip | `browser-modules-902.gz` |
| Native betroffene Vertrags-/Oberflächenprüfungen | 23 bestanden, kein Skip | `native-combined-23.gz` |
| Native Analyse | keine Befunde | `native-analysis.gz` |
| Tatsächliche Paketimporte | 16 bestanden, 21,768 s | `packaging-combined.gz` |
| Metadatenvorauswahl gegen vollständige Variantensuche | bestanden, 5,262 s | `variant-filter-equivalence.txt` |

Diese Gruppen überlappen; sie werden nicht zu einer angeblich eindeutigen
Gesamttestzahl addiert. `integration-raw-logs.json` bindet Bytezahl und SHA256
der unveränderten Streams sowie der komprimierten Dateien. Die PostgreSQL-
Datenbank wurde ausschließlich synthetisch aufgebaut. Der eigene Container
`9456d0a109bcc3f16de62150ebc5943b89e4e3bbe036f7e6b5e53ad9831d6bb5`
mit Label `smartplan.disposable=source5-positive-20261109` wurde nach Abschluss
der fünf Ausführungen identifiziert und entfernt. Keine produktive Datenbank
oder Serverinstallation wurde geändert.

## Unabhängig gefundene Fehler der vorherigen veröffentlichten CI

`ci-894-results.json` dokumentiert die abgeschlossenen Läufe auf
`894ecdde1f2d4bff89e49151b8bc9f4b5e00ffbf`. Development42624525741 besteht
sieben Jobs, der Browserjob scheitert. iPhone42624525589 scheitert an einer
nativen Testwartebedingung; der signierte Upload bleibt übersprungen.

- Browser: `login()` verlangt einen sichtbaren Identitätstext, den die echte
  390px-Ansicht per CSS ausblendet. Der Text ist korrekt vorhanden, Abmelden
  sichtbar, Anmeldung und `/me` erfolgreich; keine offenen API-Aufrufe.
  Der Helfer prüft jetzt vorhandenen exakten Text und weiterhin sichtbares
  Abmelden. Ein neuer tatsächlicher MFA-/Recovery-Mobiltest prüft beides.
- Native App: `business_accounting_year_evidence_v2_independent_review_test`
  wartet pauschal 280 ms auf echtes `File.writeAsBytes(..., flush:true)` und
  danach mit `pumpAndSettle` auf simulierte Zeit. Auf macOS war die echte
  Dateiarbeit noch nicht beendet. Die Produktoperation wartet bereits korrekt
  auf das Schreiben; die Testfolge muss die tatsächliche Future abwarten.

Die vollständigen fehlgeschlagenen Streams bleiben als
`ci-894-business-services.gz` und `ci-894-unsigned-iphone.gz` erhalten;
`ci-894-raw-logs.json` bindet deren unveränderte UTF8-Bytes. Die Korrekturen
erhalten eigene lokale Prüfungen und benötigen danach eine neue Remote-CI.
Der iPhone-Prüflauf verwendet außerdem jetzt denselben bereits vorhandenen
JSON-Fehlerzuordner wie die übrigen App-Jobs. Dadurch bezeichnet ein Fehler
den tatsächlich fehlgeschlagenen Test statt beliebiger späterer Statuszeilen.
Die vorhandenen Zuordnungs-/Interleaving-/Begrenzungsprüfungen sind erneut
ausgeführt; Rohstream `iphone-diagnostics.gz`.

## Grenzen

Der unterstützte Fall bleibt ein vollständiger ursprünglicher Bonus mit
unverändertem Brutto, laufender Rechnung und tatsächlichem Zuflusstag. Neue
positive Nettoteile erfordern belegte Vollständigkeit und dürfen zuvor
abgeführte Komponenten nicht unterschreiten. Mehrere Steuergruppen, Rückflüsse
und spätere tatsächliche Nachzahlungstage sind nicht durch diesen Vertrag
freigeschaltet. Keine reale Fach-, Geräte- oder Produktivabnahme wird behauptet.
