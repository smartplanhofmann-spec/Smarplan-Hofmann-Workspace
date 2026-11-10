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

Der tatsächliche Windows-Job129556586367 auf dem veröffentlichten Quellstand
`d083ed48f0cade4fefc989a8299e3189b7b5bd37` besteht nun einschließlich vollständiger
lokaler Pythonumgebung, nativer PDF-Prüfung, App-/Launcher-/Sicherungs-/Restoretests,
EXE, Paketierung und separatem Online-Pilotpaket. Das vollständige Windowsartefakt
13725804527 ist mit 36.436.633 Bytes und GitHub-Digest
`e0b021539901bad20fdd3fb4af7709f65fa16c0e9e94de755795c82ece539372` vorhanden.
Der separate lokale Download seines vom GitHub-Werkzeug gelieferten Dateiverweises
scheitert an Proxy-CONNECT403. Deshalb wird keine zusätzliche lokale Prüfung der
Archivbytes behauptet. [Tatsächlicher Abruf](evidence/windows-package-finish-2026-11-10/publication-observed-20261110.json).

Die vollständige CI dieses Quellstands ist noch nicht grün. Die Backendprüfung
suchte in den inzwischen zentralisierten Supportlisten nach drei Dateinamen im
Text. Sie prüft nun tatsächlich die bytegleichen Module im gebauten Support-ZIP.
Der Browser-Zeittest wählte bei einer Zweistundenschicht über Berlin-Mitternacht
den ersten, teilweise unter 30 Minuten langen Tag für einen 30-Minuten-Abzug.
Er wählt jetzt den tatsächlich längsten freigegebenen Tag; Originalintervall,
Abzug, verlorene Antwort, Wiederholungsauftrag und Gesamtprüfung bleiben gleich.
Drei Registrierungsfälle und der tatsächliche MFA-/Browserablauf bestehen lokal.
[Unveränderte Fehlerausschnitte](evidence/windows-package-finish-2026-11-10/followup-ci-failure-excerpts.txt)
bleiben getrennt von den Nachläufen erhalten. Signierung, Bedienung auf einem
realen Kundengerät und Liveinstallation bleiben eigene Nachweise.

Der abschließende [CI-Abruf](evidence/windows-package-finish-2026-11-10/publication-completed-20261110.json) bestätigt sechs erfolgreiche Development-Jobs und zwei fehlgeschlagene Prüfungen. Auch die separate unsignierte iPhone-Veröffentlichungsprüfung besteht; signierter Upload übersprungen. Der Gesamtstand wird deshalb weiterhin nicht als vollständig grün bezeichnet.
