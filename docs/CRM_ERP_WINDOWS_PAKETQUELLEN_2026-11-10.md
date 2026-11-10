# Windows-Auslieferung: gemeinsame überprüfte Paketquellen

Der vollständige Remote-Lauf des Produktstands 282d439 besteht sieben von acht
Development-Jobs und den unsignierten iPhone-Releasebuild. Die Windows-EXE
einschließlich vorheriger Tests wurde gebaut; erst **Prepare portable Windows
package** scheitert. Die tatsächliche Fehlermeldung nennt die fehlende
`business_country_rules.py`. [Unveränderter Fehlerauszug](evidence/windows-package-finish-2026-11-10/remote-failure.json),
[abgeschlossene CI-Ergebnisse](evidence/commercial-country-scope-2026-11-09/publication-completed-20261110.json).
Es wird kein vollständiger grüner Windows-Lieferstand für 282d439 behauptet.

Ursache sind drei separat gepflegte Quellenlisten: Paketprüfer, Supportarchiv
und PowerShell-Packschritt. Die neue Regeldatei war in den ersten beiden
Listen vorhanden, fehlte aber im tatsächlichen PowerShell-Kopierablauf.
Die bisherige lokale Paketprüfung übernahm ihre Dateien direkt aus der
Prüferliste und deckte diese dritte Liste nicht ab.

`native-release.py stage-local-sources --bundle <Buildordner>` übernimmt nun
genau die 163 Backend- und 213 Betreiberdateien des endgültigen Prüfers.
Der tatsächliche Windows-Workflow verwendet diesen Befehl. Das Supportarchiv
bezieht dieselben Listen aus dem gemeinsamen Modul. Die zwei langen
PowerShell-Kopierlisten und die redundanten Supportlisten entfallen.
Das ist eine Korrektur des Auslieferungswegs, keine Lockerung des Prüfers.

Vor dem ersten Schreiben werden sämtliche Quelldateien sowie alle
Zielpfadsegmente geprüft. Dateiverweise und unpassende Pfadtypen führen zur
Ablehnung; vorhandene fremde Dateien bleiben erhalten. Einzelne Dateien
werden über temporäre Nachbarn ersetzt. Nach der Übernahme prüft der
bestehende vollständige Backendprüfer Inhalte und benötigte lokale Imports.
Eine fehlende Regeldatei bleibt ausdrücklich ein Fehler. Belegarchive,
Geschäftsdaten, Datenbankmigrationen und Berechtigungen werden nicht verändert.

21 lokale Fälle bestehen ohne Auslassung: 19 Paket- und zwei Inventarfälle.
Enthalten sind die tatsächliche CLI, der anschließende unveränderte Prüfer,
vollständige Dateimengen, absichtliches Entfernen der Regeldatei, fremde
Dateiverweise, eine spät ungültige Betreiberablage und der tatsächliche Import
des entpackten Backends. Die ursprünglichen 20 Fälle des Zwischenstands bleiben
als eigener Nachweis erhalten. [Quellhashes und Rohläufe](evidence/windows-package-finish-2026-11-10/manifest.json).

Ein neuer tatsächlicher Windows-Build und sein geprüftes Lieferartefakt werden
erst nach der neuen Remoteprüfung bestätigt. Signierung, Bedienung auf einem
realen Kundengerät und Liveinstallation bleiben getrennte Nachweise.
