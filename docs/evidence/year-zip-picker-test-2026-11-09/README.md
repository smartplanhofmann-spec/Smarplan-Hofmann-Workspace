# Jahresarchiv: Test wartet auf die gesamte Dateiausgabe

Der veröffentlichte Stand `3859a1c` scheiterte im Flutter-Job
`129219853750`: Nach dem zweiten echten ZIP-Abruf erwartete der Test einen
abgeschlossenen Speichervorgang, beobachtete aber noch null. Das unveränderte
CI-Log liegt als ursprünglicher JSON-String in `ci-original.json`.

Die bisherige Testhilfe betrachtete acht Durchläufe ohne aktive HTTP-Anfrage
als Abschluss. Die vom Test eingesetzte Ausgabefunktion prüft anschließend
jedoch erneut die Berechtigung und schreibt asynchron mit
`File.writeAsBytes(..., flush: true)`. Dieser Schritt war nicht in den
HTTP-Zähler eingeschlossen. Die CI-Angabe `reads 2/7` passt zu dieser Lücke;
das Log allein zeigt nicht den genauen wartenden Stack. Die tatsächliche
Synchronisationslücke ist unabhängig davon kontrolliert reproduziert.

Der negative Nachweis `reproducer-before-fix.json` bewahrt den Logtext als
JSON-String einschließlich seines ursprünglichen Leerraums. Er verwendet den vorhandenen
echten HTTP-/ZIP-Ablauf und einen gehaltenen Dateischreibschritt. Mit der
alten Wartebedingung schlägt er nach 21 Sekunden mit Exit 1 fehl:
`HTTP-idle must not finish before the actual file output.` Der zugehörige
vollständige Testquellstand liegt in `reproducer-before-fix.dart.txt`.

Geändert sind ausschließlich die beiden HTTP-Testdateien für v1 und v2.
Der Test zählt nun den gesamten Ausgabecallback in einem `try/finally` und
wartet zusätzlich darauf, dass die Jahresnachweis-Aktionen nicht mehr als
beschäftigt/deaktiviert angezeigt werden. Das deckt auch die Phase vor
Eintritt in den Callback ab. Der bestehende Schleifenrahmen, die acht ruhigen
Durchläufe und die Vier-Minuten-Testfrist bleiben unverändert.

Die Regression prüft zwei getrennte Phasen: Ein Gate hält die Antwort nach
einem echten ZIP-Read, während HTTP- und Callback-Zähler bereits null sind,
die Oberfläche aber noch beschäftigt ist. Ein zweites Gate hält die echte
Dateiausgabe nach der Berechtigungsprüfung. Beide bleiben länger als acht
Durchläufe geschlossen. Ein einziger Polltreiber gibt sie frei; es gibt keine
verschachtelten `runAsync`-Aufrufe. `finally`-Blöcke geben auch bei
fehlgeschlagenen Assertions alle Gates frei und beenden offene Ausgaben vor
dem Abbau der Testdateien.

Zusätzlich bleiben bzw. sind tatsächlich geprüft:

- verlorene ZIP-Antwort nach echtem Abruf und erneute Originalprüfung;
- Entzug nur eines enthaltenen Projektleserechts bei offenem Picker;
- echter Dateisystemfehler beim Schreiben auf ein Verzeichnis, ohne Änderung
  des bereits gespeicherten ZIPs;
- Schließen der alten Ansicht bei offenem Picker: keine späte Ausgabe und
  keine Änderung der Nachfolgeansicht;
- bytegleicher ZIP-Erhalt, SHA-256 und unabhängiger Python-Archivprüfer;
- keine fachlichen POSTs durch den Exportleser.

Beide erweiterten echten HTTP-Tests bestehen mit Exit 0 in 48 Sekunden
(`final-http-tests.txt`). Die gezielte Dart-Analyse meldet keine Befunde
(`analysis.txt`). Der anfängliche Nachlauf nur mit Exportzähler bleibt in
`after-export-counter.txt` getrennt vom endgültigen Nachweis erhalten.

Die Befehle liefen in einer eigenen Arbeitskopie mit Flutter 3.47.7, Dart
3.13.5, dem vorhandenen Clang-Pfad und der vorhandenen Python-Umgebung:

```bash
SMARTPLAN_TEST_PYTHON=/workspace/Smarplan-Hofmann-Workspace/.venv/bin/python \
PUB_CACHE=/workspace/toolchains/pub-cache \
PATH=/workspace/toolchains/clang-19/bin:$PATH \
/workspace/toolchains/flutter/bin/flutter test --no-pub --reporter expanded \
  --concurrency=1 test/business_accounting_year_evidence_http_test.dart \
  test/business_accounting_year_evidence_v2_http_test.dart

PUB_CACHE=/workspace/toolchains/pub-cache \
/workspace/toolchains/flutter/bin/dart analyze \
  test/business_accounting_year_evidence_http_test.dart \
  test/business_accounting_year_evidence_v2_http_test.dart
```

Es wurden keine Produktdateien, Backendfixtures, Rechteprüfungen oder
Zeitlimits geändert. Die Ausgabefunktion ist ein Testadapter mit echtem
Dateischreiben; ein nativer Betriebssystem-Dateidialog oder eine neue
Serverinstallation wird damit nicht als getestet behauptet. Die
Dateihashes und die unveränderten Fixture-Präfixe stehen in `verification.json`.
