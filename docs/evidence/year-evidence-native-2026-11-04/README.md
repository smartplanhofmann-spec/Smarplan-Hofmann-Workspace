# Native Jahresnachweise v1 – Abnahme vom 04.11.2026

`manifest.json` bindet die endgültigen Quellen, Tests, tatsächliche Fixture und Nachweise. `runtime-freeze.json` benennt die drei eingefrorenen Runtime-Dateien, zwei eigenen Tests und unveränderten gemeinsamen Hilfen.

- `final-acceptance-49.txt`: 49/49, davon 21 neue Vertrags-/Lifecyclefälle, ein tatsächlicher HTTP-/Dateiablauf bei 390×844 und 27 bestehende EÜR-/Accountingfälle.
- `final-analysis.txt`: keine statischen Probleme in den fünf eigenen/geänderten Dartdateien.
- `baseline.json` und `integration.patch`: tatsächlicher Ausgangsstand und enger zusätzlicher EÜR-Einstieg. Den Patch bei Integration unter Erhalt neuerer Altposten- und anderer EÜR-Einstiege übernehmen.
- `runtime-freeze-before-final-offline-boundary.json` sowie `*-before-fixture-freeze.txt`: ausdrücklich historische Zwischenstände. Sie sind keine endgültige Freigabe.

Die abschließenden Tests verwenden die echte sechsfach-Backendfixture mit SHA-256 `a859f2bbbcfab6f890c2968a05aa2fa839299117ae43b8e15e2d7852c82d36a0` (719679 Byte). Der tatsächliche HTTP-Fall erzeugt zusätzlich ein neues reales Archiv, bindet es an den ursprünglichen EÜR-Export, prüft Größe und Hash, schreibt es und ruft den unabhängigen lokalen Prüfer mit dem separat authentisierten SHA auf. Ein projektbezogener Quellenrechteentzug nach Dateiauswahl verhindert die zweite Ablage trotz weiterhin vorhandener globaler Rechte.

Der archivierte Hash beweist keine intrinsische Vollständigkeit aller historischen Quellenabhängigkeiten. `intrinsic_dependency_closure=false` bleibt eine ausdrückliche Grenze; Offlineprüfung setzt den separat aufbewahrten, authentisierten Archivhash voraus. Die Oberfläche beschreibt dies und trennt die damalige Aussage des EÜR-Reports von einer unabhängigen Vollständigkeitsprüfung. Betriebssystemdialoge sind im HTTP-Test kontrolliert ersetzt; kein Mobilgerätetest.

Keine Backendänderung, Produktivkontakte, Mainänderung oder Commits. Ein unabhängiger Review und Roots Integration folgen getrennt. V2-Jahresvortragsquellen sind nicht Bestandteil dieses Nachweises.
