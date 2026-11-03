# Flutter-Gesamtprüfung vom 03.11.2026

## Abschließender integrierter Lauf

Nach Integration und gezielter Prüfung der finalen Bank-, Midijob- und
Retourenclients wurde der gesamte unveränderte Testbaum erneut ausgeführt.
Dieser zweite vollständige Lauf ist erfolgreich abgeschlossen:

| Nachweis | Tatsächliches Ergebnis |
| --- | --- |
| `flutter analyze --no-pub` über die ganze App | Ohne Befund, 6,2 Sekunden |
| `flutter test --no-pub --machine test` | 98 Suiten, 848 abgeschlossene Tests |
| Bestandene Tests | 848 |
| Fehlgeschlagene / übersprungene Tests | 0 / 0 |
| Laufzeit laut Runner | 228,669 Sekunden |
| Exitstatus / Runnerabschluss | 0 / `success:true` |
| Geänderte oder ergänzte App-/Testdateien während des Laufs | Keine |
| Separate stderr-Ausgabe | Leer |

Start war am 03.11.2026 um 21:25:28 UTC. Git-Basis blieb
`49369da1eb0c36cfa2ef7c0eefa6337aebe636c8` zuzüglich des gemeinsamen
Entwicklungsstands. Der SHA-256 des Startmanifests aller Dartquellen, Testdateien
und beider Pubspec-Dateien lautet
`6127c73a10b409c83ad2e87a430f01e2ec425bffc9e9b4c9cb2b231fa439ffdd`.
Werkzeugkette und Ausführungsparameter entsprechen dem unten dokumentierten
Erstlauf. Es wurden keine Tests ausgeschlossen, übersprungen oder abgeschwächt.

Der grüne Abschluss belegt den gesamten Flutter-Testbaum einschließlich der
aktuell integrierten Funktionen und der vorhandenen echten Backend-/HTTP-Tests.
Eine tatsächliche Windows-/iPhone-Geräteabnahme oder ein Windows-Produktbuild
ist damit nicht belegt. Die eigenständigen echten Browserabläufe sind in den
jeweiligen Clientberichten dokumentiert.

## Vorangegangener integrierter Erstlauf

Der vollständige Testbaum `app/test/` wurde nach dem syntaktisch vollständigen
Erststand des Bankabgleichclients geprüft. Es wurden keine Tests ausgeschlossen,
übersprungen oder durch pauschale Freigaben abgeschwächt.

| Nachweis | Tatsächliches Ergebnis |
| --- | --- |
| `flutter analyze --no-pub` über die ganze App | Ohne Befund, 5,1 Sekunden |
| `flutter test --no-pub --machine test` | 96 Suiten, 835 abgeschlossene Tests |
| Bestandene Tests im Erstlauf | 827 |
| Fehlgeschlagene Tests im Erstlauf | 8 |
| Übersprungene Tests | 0 |
| Laufzeit laut Runner | 222,776 Sekunden |
| Exitstatus des Erstlaufs | 1; Runner `success:false` |

Der Lauf startete am 03.11.2026 um 20:58:14 UTC. Git-Basis war
`49369da1eb0c36cfa2ef7c0eefa6337aebe636c8`, ergänzt um den bestehenden gemeinsamen,
noch nicht committeden Entwicklungsstand. Das Startmanifest umfasst alle
Dartquellen, Testdateien sowie `pubspec.yaml` und `pubspec.lock`; sein SHA-256 ist
`de52ee30fbe80d6674b3c068129f81a5d29b15170af2fdfeb745b0710a838d4f`.

Verwendet wurden Flutter 3.47.7, Dart 3.13.5, der bestehende Pub-Cache und die
vorhandene Clang-19-Werkzeugkette. `--no-pub` verhinderte eine unbeabsichtigte
Änderung der aufgelösten Paketversionen. Lokale Testsockets und vorhandene echte
Backend-/HTTP-Integrationstests liefen in der bereitgestellten Cloud-Umgebung.

## Acht Erstbefunde, zwei Ursachen

**Bankabgleich: ein Widgettest.**
`bank binding defaults all factual choices empty and activation unconfirmed`
fand bei `coverage_from` und `coverage_to` eine Anzeige statt leerer Eingabe.
Die neue Bankseite hatte `initial:''` verwendet; der gemeinsame Datumseditor
formatierte diesen leeren Text als „Nicht angegeben“. Die verantwortliche
Bankimplementierung änderte beide Vorbelegungen zu `initial:null`. Am gemeinsamen
Editor oder der Session war dafür keine Änderung erforderlich. Der zuständige
Clientlauf bestätigte anschließend **10/10 Banktests bestanden**. Der anschließende finale Bankclientstand ergänzt sichtbare Berichtszeilen,
deutsche Problembeschriftungen und MIME-Charset-Normalisierung für Exporte.
Dessen abschließender Modulnachweis bestätigt **11/11 Banktests** und eine
statische Analyse ohne Befund in 5,0 Sekunden; siehe
[CRM_ERP_BANKABGLEICH_CLIENTS.md](CRM_ERP_BANKABGLEICH_CLIENTS.md).

**Portalrechte: sieben Widgettests.** Die Testauswahl suchte noch
„Angebotsportal verwalten“. Das implementierte gemeinsame Recht heißt nach der
Kundenportalerweiterung „Angebots- und Kundenportal verwalten“. Der Scrollfinder
fand deshalb keinen Eintrag und beendete die Tests vor den Fachaktionen.

Geändert wurde ausschließlich die veraltete Testbeschriftung in
`app/test/business_permissions_test.dart`. Alle Berechtigungs-, Scope-,
Revisions-, Rechteverlust- und Wiederholungsprüfungen bleiben erhalten.
Die vollständige gezielte Rechtesuite besteht danach **11/11 Tests**,
einschließlich der 390- und 1200-Pixel-Ansichten. Es wurde keine Session- oder
Produktberechtigungslogik gelockert.

## Einordnung der Korrekturen

Der dokumentierte Erstlauf bleibt ein fehlgeschlagener Gesamtlauf. Die beiden
gezielten grünen Nachprüfungen sind Korrekturbelege; sie werden nicht als neuer
835/835-Gesamtlauf ausgegeben. Während des Laufs änderte sich ausschließlich die
Bankdatei; anschließend wurde die genannte Testbeschriftung korrigiert.

Der oben dokumentierte zweite vollständige Lauf erfolgte nach Integration der
Retouren- und Midijobclients und prüft diesen neuen zusammenhängenden Stand.
Die erste Testausführung meldete eine fehlende Visual-Studio-C++-Komponente auf
stderr; sie verhinderte keinen der damaligen 835 Tests und erzeugte keinen Skip.
Die separate stderr-Datei des abschließenden Laufs ist leer.

## Laufartefakte

Die genauen maschinenlesbaren Ergebnisse bleiben in `work/verification/`:

- `flutter-final-snapshot.json`: vollständiges Startmanifest des Abschlusslaufs.
- `flutter-final-regression.jsonl`: alle Runnerereignisse des Abschlusslaufs.
- `flutter-final-regression-summary.json`: 848 Erfolge, keine Fehler/Skips,
  erfolgreicher Runnerabschluss und nachgewiesen unveränderter Quellstand.
- `flutter-final-regression.stderr.log`: leere separate stderr-Ausgabe.
- `flutter-final-analyze.log`: vollständige statische Analyse ohne Befund.
- `flutter-full-snapshot.json`: Startdateien und Prüfsummen.
- `flutter-full-regression.jsonl`: vollständige Runnerereignisse.
- `flutter-full-regression-summary.json`: Zählung, einzelne Fehler, keine Skips,
  Runnerabschluss und Änderungen gegenüber dem Startmanifest.
- `flutter-full-regression.stderr.log`: separate stderr-Ausgabe.
- `flutter-full-analyze.log`: vollständige statische Analyse.
- `flutter-permissions-regression-fix.log`: 11/11 Rechteprüfungen nach Labelkorrektur.
- `bank-clients-flutter.log`: gezielter Banknachweis des verantwortlichen Clients.

Die Laufartefakte sind lokal; dieser Bericht und die unveränderten beziehungsweise
gezielt korrigierten Tests bilden den permanenten Nachweis im Repository.
