# Unabhängiger Clientreview des Jahresnachweises V2

Die beiden eingefrorenen Reader bestehen **acht zusätzliche Browserfälle und acht zusätzliche Native-Fälle**. Die Analyse der neuen Dart-Testdatei meldet **0 Probleme**. Kein neuer Produktfehler wurde bestätigt; keine Produktdatei wurde durch diesen Review geändert.

Prüfbaum: `/workspace/smartplan-year-review-export-carryover-20261104`. Die tatsächliche vierteilige Backendfixture hat SHA-256 `2f9a1664eb1bf1d2615c7f25de9673aba4dc8ee95acad32367588411ba9f64d5`. Die separat dokumentierten neun unabhängigen Backendfälle bleiben unverändert in `docs/evidence/year-package-v2-independent-backend-2026-11-04/manifest.json` gebunden.

## Enge Produktänderung

Die 23 Dateien der übernommenen V1-Clientbaseline sind in `work/verification/year-package-v2-client-v1-baseline.json` gebunden (SHA-256 `fac8bd6768135aa34cc24544d2cf64c866ad4a04a1b13007bd2cffa4546f6975`). Die unabhängige Prüfung bestätigt: Nur zwei Reader unterscheiden sich. Beide erlauben zusätzlich den ausdrücklich bekannten Formatwert `smartplan-year-evidence-v2`. Die bisherigen Export-, Hash-, Größen-, Rechte-, Kontext-, Dialog- und Dateiausgabeprüfungen bleiben erhalten. Alle übrigen übernommenen Dateien sind bytegleich.

| Reader | Geprüfter, vom Owner bestätigter eingefrorener SHA-256 |
| --- | --- |
| `app/lib/business_accounting_year_evidence_contract.dart` | `d0e2bb02e1bd46f50ef04abba3c06c54c9f29f23e11c7669190629e6bab19c11` |
| `web/office/accounting-year-package-contract.js` | `4459c3580c3da8ede338d33ec567901d8117620e99c6670c1c74e8b639cc4b73` |

## Zusätzliche Gegenfälle

Die Browserprüfung liest alle vier tatsächlichen V2-Szenarien: offener ursprünglicher Prüfstand, Teildeckung, vollständige Historie und derselbe alte Teilstand nach späterer Korrektur. Sie bindet den jeweiligen ursprünglichen Export, die authentisierten Metadaten und die exakten ZIP-Bytes. Verwechslungen mit sämtlichen sechs gespeicherten V1-Szenarien werden abgewiesen; die sechs gültigen V1-Pakete bleiben mit dem neuen Reader lesbar. Der alte Teilstand bleibt bytegleich. Ein Wechsel des bekannten Formats oder des Archivhashes nach dem ersten Metadatenabruf scheitert, ebenso veränderte ZIP-Bytes und eine falsche Vollständigkeits-/Privatsphärenangabe.

Die Native-Prüfung liest dieselben vier tatsächlichen Szenarien und prüft dieselbe historische Bytegleichheit. Drei zusätzliche Widgetfälle führen den tatsächlichen Desktop-Produktpfad aus; nur die Antwort des Plattform-Dateidialogs wird gesteuert, der `exportFile`-Testhook wird nicht verwendet:

1. Vollständige V2-Historie wird nach erneuter Prüfung tatsächlich in eine temporäre Datei geschrieben; sämtliche Bytes stimmen mit dem ursprünglichen Backendarchiv überein.
2. Während der Dateiauswahl wird der Metadatenformatwert von V2 auf den ebenfalls bekannten V1-Wert geändert. Die gebundene alte Antwort darf nicht ersetzt werden: keine Datei und keine Erfolgsmeldung.
3. Während V2-ZIP-Bytes ausstehen, wird ein tatsächlicher unvollständiger V1-Export ausgewählt. Die verspätete V2-Antwort öffnet keinen Speicherdialog und überschreibt weder die neue Ansicht noch deren Unvollständigkeitskennzeichnung.

Es wurden keine Schreibbefehle an das Backend gesendet. Dateien und Testkonten sind synthetisch. Die bereits geprüfte Außenankergrenze bleibt unverändert: SHA-256 stammt aus dem berechtigten Originalexportabruf; ein Archiv mit seinem selbst gelieferten Ersatzhash authentisiert seine Herkunft nicht. `intrinsic_dependency_closure=false` wird nicht durch den Readeranschluss aufgehoben.

## Reproduktion

Browser, Arbeitsverzeichnis `web/office`:

```sh
node --test --test-isolation=none --test-reporter=spec \
  tests/accounting-year-package-v2-independent-review.test.mjs
```

Der benannte Lauf weist acht bestandene Einzeltests aus. Der vorherige normale Node-Lauf meldete nur die bestandene Datei als eine Einheit und wird deshalb nicht als Nachweis der acht Einzeltestnamen verwendet.

Native, Arbeitsverzeichnis `app`:

```sh
PATH=/workspace/toolchains/clang-19/bin:$PATH \
PUB_CACHE=/workspace/toolchains/pub-cache \
SMARTPLAN_TEST_PYTHON=/tmp/smartplan-backend-verified/bin/python \
/workspace/toolchains/flutter/bin/flutter test --no-pub \
  test/business_accounting_year_evidence_v2_independent_review_test.dart \
  --reporter expanded

PUB_CACHE=/workspace/toolchains/pub-cache \
/workspace/toolchains/flutter/bin/cache/dart-sdk/bin/dart analyze \
  test/business_accounting_year_evidence_v2_independent_review_test.dart
```

Eigener Manifest- und Lognachweis: `docs/evidence/year-package-v2-independent-clients-2026-11-04/manifest.json`. Die eigenen Browserfälle sind Vertragsprüfungen; der eigene Native-Pfad verwendet echte Datei-I/O mit kontrollierter Plattformantwort. Die vom Owner separat ausgeführten V2-Browser-/HTTP-Abläufe, die Gesamtintegration und die tatsächlichen Windows-/iOS-Geräteprüfungen werden hier nicht als eigene Ergebnisse ausgegeben. Kein PostgreSQL, kein Commit und keine Änderung am Hauptprojekt.
