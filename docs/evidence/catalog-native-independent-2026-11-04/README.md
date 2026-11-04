# Unabhängiger Native-Katalog-v2-Review · 04.11.2026

Geprüfter Baum: `/workspace/smartplan-catalog-prices-v2-20261104`. Gegenstand ist der eingefrorene native V2-Stand aus `docs/evidence/catalog-prices-native-2026-11-04-handoff.json`. Der Reviewer hat keine Produktdatei geändert und keinen Commit angelegt.

## Ergebnis

- **17 neue unabhängige Widgetfälle** in `app/test/business_catalog_prices_independent_lifecycle_test.dart`.
- **87/87** im finalen gemeinsamen Lauf: 17 Reviewfälle plus die 70 Fälle der fünf gezielten nativen V2-Testdateien, einschließlich zweier tatsächlicher lokaler Python/HTTP-Tests.
- Dart-Analyse der neuen Testdatei: **0 Befunde**.
- Enger Backend-Nachtrag: die **12 unveränderten unabhängigen Backendfälle plus 5 Purchasingfälle sind 17/17 grün** (2,150 s).
- Kein neuer Produktbefund; alle neun nativen Produktdateien, die fünf Originaltestdateien und die echte Fixture stimmen beim Abschluss exakt mit dem finalen Owner-Handoff überein.

## Zusätzliche Gegenfälle

Die eigene Testdatei prüft erfolglose und erfolgreiche verspätete Kandidatenantworten nach Rollenwechsel. Vor tatsächlicher Preisübernahme und Originalexport werden entzogene Rechte auch dann erkannt, wenn der Client zuvor keine Sitzungsbenachrichtigung erhalten hat. Ein zwischen Auflistung und Auswahl nicht mehr verfügbarer Preis wird nicht als Belegposition übernommen.

Sechs Fälle halten eine tatsächliche Beleg-Speicheranfrage offen und ersetzen danach die Sitzung, ändern deren Generation oder entziehen das Leserecht. Erfolg und Fehler dürfen bei 390 × 844 Pixeln weder in eine alte Belegseite navigieren noch alte Texte erneut anzeigen. Zwei parallel offene globale Belegaufträge werden ausschließlich durch die ausdrückliche Projektwahl zugeordnet; nur der gewählte Originalauftrag wird mit identischer Nonce wiederholt, der andere bleibt offen. Es erfolgt keine neue Preiswahl.

Zwei Kalkulationsfälle verwerfen verspätete Vorschauantworten nach Projektwechsel. Zwei Bestellfälle prüfen angenommene Antworten nach Hintergrundwechsel. Der verlorene Bestell-ACK wird anschließend nach Entzug und erneuter Erteilung des Schreibrechts mit exakt demselben Originalbody und derselben Nonce wiederholt: ein gespeicherter Effekt, keine zusätzliche Kandidatenauswahl und anschließend kein offener Auftrag.

Die unabhängigen Lifecyclefälle verwenden kontrolliert verzögerte Transportantworten und die tatsächliche Domainfixture. Sie sind kein eigenständiger physischer Geräte- oder End-to-End-Nachweis. Der kombinierte Lauf führt zusätzlich die vorhandenen tatsächlichen lokalen HTTP-Strecken für Originaldatei, gebundene Vorschau, datierte Belegübernahme, verlorene ACKs sowie die exakten JSON-Größengrenzen aus. Keine Produktivkontakte.

## Backend-Nachtrag

`Purchasing._source` prüft im V2-Zweig die vollständige ursprüngliche Artikelversion intrinsisch, einschließlich Revision, ursprünglicher Eigenschaften und Hash, statt den heutigen Artikelkopf zu verlangen. Die Restoreprüfung erfasst nun auch noch nicht extern bestätigte V2-Vorschläge. Die wiederholten Fälle weisen manipulierte Revision 999, ursprünglichen Namen und Kosten zurück und erhalten die zulässige alte Bestellung trotz heutiger Stammdatenänderungen. V1 bleibt im unveränderten Zweig.

Dieser Nachtrag ersetzt nicht den früheren 103er-Reviewstand unter `docs/evidence/catalog-independent-review-2026-11-04/`. Dessen Hashes dokumentieren den damaligen Abschluss; die aktuellen Nachtragshashes stehen im neuen Manifest. Das additive Feld `candidates.source_reference` ändert keine unveränderlichen Preis-/Snapshot-/Quittungshashes.

## Reproduktion

Im Verzeichnis `app`:

```sh
PATH=/workspace/toolchains/clang-19/bin:$PATH PUB_CACHE=/workspace/toolchains/pub-cache SMARTPLAN_TEST_PYTHON=/tmp/smartplan-backend-verified/bin/python /workspace/toolchains/flutter/bin/flutter test --no-pub --reporter expanded test/business_catalog_prices_independent_lifecycle_test.dart test/business_catalog_prices_test.dart test/business_catalog_prices_lifecycle_test.dart test/business_catalog_price_consumers_test.dart test/business_catalog_price_workflows_test.dart test/business_catalog_prices_http_test.dart
PATH=/workspace/toolchains/clang-19/bin:$PATH PUB_CACHE=/workspace/toolchains/pub-cache /workspace/toolchains/flutter/bin/dart analyze test/business_catalog_prices_independent_lifecycle_test.dart
```

Im Verzeichnis `backend`:

```sh
PYTHONPATH=.:online:business_tests /tmp/smartplan-backend-verified/bin/python -m unittest -v test_catalog_prices_independent_review test_business_catalog_prices_purchasing
```

`test-harness-initial.txt` dokumentiert vier anfängliche Fehler der neuen Teststeuerung: zwei falsche Buttonbeschriftungen und zweimal `pumpAndSettle` während eines absichtlich offenen Hintergrund-Spinners. Korrigiert wurden nur diese Testselektoren bzw. das gezielte Pumpen, keine Laufzeitdatei. Dieser Log ist ausdrücklich kein roter Produktnachweis. Der finale Log gehört zur im Manifest gehashten endgültigen Testdatei.
