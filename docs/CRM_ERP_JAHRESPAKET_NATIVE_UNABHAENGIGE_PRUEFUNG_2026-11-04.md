# Unabhängige Prüfung des nativen Jahresnachweises – 04.11.2026

Der eingefrorene native V1-Vertrag besteht die zusätzlichen **16 unabhängigen Prüfungen**. Zusammen mit dem unveränderten echten HTTP-Test des Implementierungsverantwortlichen sind **17/17 Fälle grün**; die Analyse der neuen Testdatei meldet **0 Probleme**. Es wurde kein Produktfehler bestätigt und keine Produktdatei geändert.

Prüfbaum: `/workspace/smartplan-year-review-export-20261104`. Grundlage ist der native Handoff `docs/evidence/year-evidence-native-2026-11-04/manifest.json` mit SHA-256 `9430514d6c59a7a5143a2f54529e017a76d627fc227a34c5cf3c292f99a681a6`. Die tatsächlich gelesene und verwendete Backendfixture `app/test/fixtures/accounting_year_package_v1.json` hat SHA-256 `a859f2bbbcfab6f890c2968a05aa2fa839299117ae43b8e15e2d7852c82d36a0`.

## Unabhängiger Prüfweg

Die neue Datei `app/test/business_accounting_year_evidence_independent_review_test.dart` verwendet die tatsächlichen ursprünglichen EÜR-Exporte, Metadaten und ZIP-Bytes der Backendfixture. Lediglich API-Antwortzeitpunkte und die Plattformgrenze des Dateiauswahldialogs werden gesteuert. Der `exportFile`-Testhook wird in diesen Tests nicht verwendet: Dateiauswahl, erneute asynchrone Berechtigungsprüfung und `File.writeAsBytes(..., flush: true)` laufen über den tatsächlichen Desktop-Produktpfad. Es entstehen ausschließlich temporäre synthetische Dateien; diese werden nach dem Test entfernt.

| Prüfung | Nachgewiesenes Verhalten |
| --- | --- |
| Historischer Export nach späterer Profiländerung | Gespeicherte ZIP-Bytes stimmen vollständig mit dem alten Original überein. Die abschließende Prüfung verwendet dessen serverseitig gebundenen Archivhash. |
| Einzelnes Quellrecht während Dateiauswahl entzogen | Globales `finance.read` bleibt bestehen; die erneute Quellenprüfung scheitert, kein ZIP wird geschrieben, alte Metadaten verschwinden. |
| Archivhash während Dateiauswahl ersetzt | Der neu angebotene Hash darf den bereits gelesenen ursprünglichen Metadatenstand nicht ersetzen; keine Ausgabe. |
| Sitzung, Export, Token, Hintergrund oder Entfernen der Seite während Dateiauswahl | Der verspätete Dialogabschluss schreibt keine alten Bytes und behauptet keinen Erfolg. Ein neu gewählter unvollständiger Export behält seine eigene Kennzeichnung. |
| Echter Schreibfehler | Ein bestehendes Verzeichnis als Ziel löst einen tatsächlichen Dateisystemfehler aus; kein Erfolgshinweis und keine weiterverwendeten alten Metadaten. Nach erneutem Lesen speichert ein gültiges Ziel die Originalbytes. |
| Abbruch der Dateiauswahl | Keine Datei, keine Erfolgsmeldung, ursprüngliche Metadaten bleiben korrekt sichtbar. |
| Verspäteter initialer Originalabruf | Ein Wechsel von Token, Hintergrundzustand, Sitzung oder Export verhindert die Wiederherstellung alter Metadaten. |
| Fremder ursprünglicher Export trotz erfolgreicher HTTP-Antwort | Die falsche Antwort wird vor dem Abruf von Archivmetadaten und vor einer Dateiauswahl abgewiesen. |
| Veränderte ZIP-Bytes bei gleichem ursprünglichen Außenanker | Keine Dateiauswahl und keine Ausgabe; die Datei darf ihren Vertrauensanker nicht selbst ersetzen. |

Der gemeinsam erneut ausgeführte unveränderte HTTP-Test navigiert bei 390 Pixeln Breite vom echten EÜR-Journal zum ursprünglichen Export, liest echte Backendbytes, wiederholt einen verlorenen Download, speichert nach erneuter Prüfung und entzieht anschließend ausschließlich ein benötigtes projektbezogenes Finanzleserecht. Das globale Finanzleserecht bleibt dabei erhalten. Die zweite Ausgabe wird verhindert. Die erste gespeicherte Datei besteht den Offlineprüfer mit dem separat vom authentisierten Metadatenabruf übernommenen Archivhash; das Ergebnis enthält ausdrücklich `intrinsic_dependency_closure=false`.

## Vertrauensgrenze

Geprüft ist der bewusst begrenzte Außenanker-Vertrag: Der Client bindet die unveränderten Archivbytes an die zuvor über den berechtigten Originalexportabruf erhaltenen Metadaten und deren SHA-256. Er übernimmt keinen im ZIP mitgelieferten Ersatzanker. Die angezeigte Warnung stellt klar, dass dies keine eigenständige Vollständigkeit sämtlicher Belegabhängigkeiten beweist. Ein Archiv samt fremdem, ebenfalls übernommenem Hash kann seine Herkunft nicht selbst authentisieren; die bereits dokumentierte Backendgrenze wird durch den Client nicht aufgehoben.

## Reproduktion und Nachweise

Im Unterverzeichnis `app`:

```sh
PATH=/workspace/toolchains/clang-19/bin:$PATH \
PUB_CACHE=/workspace/toolchains/pub-cache \
SMARTPLAN_TEST_PYTHON=/tmp/smartplan-backend-verified/bin/python \
/workspace/toolchains/flutter/bin/flutter test --no-pub \
  test/business_accounting_year_evidence_independent_review_test.dart \
  test/business_accounting_year_evidence_http_test.dart --reporter expanded

PUB_CACHE=/workspace/toolchains/pub-cache \
/workspace/toolchains/flutter/bin/cache/dart-sdk/bin/dart analyze \
  test/business_accounting_year_evidence_independent_review_test.dart
```

Der endgültige gemeinsame Lauf endet nach neun Sekunden mit `+17: All tests passed!`. Die Logs und gelesenen Quellhashes liegen in `docs/evidence/year-evidence-native-independent-2026-11-04/manifest.json`. Der erste unabhängige Versuch hatte fünf Fehler im neu geschriebenen Testablauf: Echte Datei-I/O und der außerhalb der Widget-Fake-Uhr erzeugte Dialog-Future waren noch nicht vollständig abgearbeitet. Nur dieser Testhelper wurde korrigiert; sämtliche Behauptungen über Ausgabe und Rechte blieben bestehen. Der ursprüngliche Fehlversuch bleibt als Nachweis erhalten. Der anschließende reine 16er-Lauf und der abschließende 17er-Lauf sind grün.

Die echten Betriebssystemdialoge auf Windows und das iOS-Teilen-Menü wurden hier nicht auf einem Gerät ausgeführt. Die Prüfung ersetzt weder diese Geräteabnahme noch die noch getrennte Gesamtintegration. Kein PostgreSQL-Lauf, keine echte Zahlung, keine neue Buchung, keine Backendänderung, kein Commit und keine Änderung am Hauptprojekt erfolgten in diesem Review.
