# Vollständige technische Prüfgruppen

Der Gesamtauftrag bleibt aktiv. Dieser Abschnitt verbessert den reproduzierbaren
technischen Gesamtnachweis A–G; er erklärt keine fachliche oder produktive
Gesamtabnahme für erledigt. Basis ist der gemeinsam geprüfte Altprotokollstand
d22dea7756b29bb5c1bef2dd5f18c15a7fa2fb0d auf veröffentlichtem799c144.

## Konkreter Befund

Die bisherige zentrale Prüfung führt76 ausdrückliche Online-Unittestaufrufe
sowie69 Browserabläufe nacheinander aus. Die wildcardbasierten Aufrufe umfassen
aktuell154 einzelne Datei-/Modulauswahlen. Neue Zwischenstände können die lange
CI noch vor einem vollständigen gemeinsamen Ergebnis ablösen. Die bestehende
Abbruchregel wird erhalten; die tatsächlich unabhängigen Prüfungen werden auf
je sechs Gruppen mit eigenen PostgreSQL-Diensten verteilt.

Zusätzlich fehlen neun bereits implementierte und gezielt ausführbare Abläufe
in der zentralen Browser-CI: accounting-allocation, accounting-capacity,
accounting-components, accounting-profile, accounting-refunds,
accounting-refunds-v2, planning-relogin, purchasing-catalog und purchasing-receipts.
Die neue Auswahl enthält deshalb78 tatsächliche Browserabläufe. Sie ersetzt
keine bisherige Prüfung. Die vollständigen Browsermodul- und kommerziellen
Backendprüfungen bleiben zusätzlich einmal verpflichtend.

## Vertrag

[scripts/ci-check-plan.json](../scripts/ci-check-plan.json) hält die bisherigen
expliziten Auswahlen und die zusätzlichen Browserabläufe fest. Wildcards werden
vor der Verteilung gegen tatsächliche Dateien aufgelöst; eine leere Auswahl
schlägt fehl. Jede Auswahl gehört exakt einer Gruppe, keine Gruppe ist leer.
Jeder Aufruf verwendet wie bisher einen eigenen Prozess. Für die Onlinegruppe
ist ein ausdrücklicher Wegwerf-DSN verpflichtend; echte Einzeltests prüfen ihre
eigenen Datenbank-/Rollen-/Firmenwächter weiter. Vollständige Python-Suchpfade
enthalten sowohl bisherige direkte Testimporte als auch das Paket backend.

Der Runner entfernt geerbte Browserziele und gibt den Datenbankselektor nur an
den tatsächlichen PostgreSQL-Rechnungsablauf weiter. Alle anderen Browserfixtures
bleiben bei ihrer eigenen lokalen Datenhaltung. MFA, echte HTTP-Antworten,
Sandbox und originale Fachprüfungen bleiben erhalten. Jeder Ablauf bekommt ein
eigenes Screenshotverzeichnis. Fehler beenden die übrigen unabhängigen
Auswahlen nicht; sie machen die ganze Gruppe weiterhin rot. Exakte Auswahl,
Teilfortschritt, Endstatus und einzelne rohe Logs werden auch bei Fehlern als
getrennte Gruppenartefakte erhalten. Es gibt kein continue-on-error.

Der bisherige tatsächliche HTTPS-/Worker-Runtimetest bleibt mit identischen
Befehlen genau einmal in einem eigenen Job mit frischer PostgreSQL-Instanz. Update-, HTTPS-, Backend-, Flutter- und
beide nativen Buildkonfigurationen bleiben unverändert. Weder Fachregeln noch
Signierung, Auslieferungsziel oder echte Betriebsdaten werden geändert.

## Tatsächlicher Prüfstand während der Arbeit

Sieben Auswahl-/Fehler-/Prozessverträge bestehen. Sie vergleichen die aktuelle
Auswahl unabhängig mit der eingefrorenen vorherigen Workflowdatei, prüfen die
vollständige Browserzielmenge und beweisen mit wirklich ausgeführten Kindern,
dass Exit7 rot bleibt, der nächste Aufruf trotzdem läuft und fremde Ziel-/
Datenbankselektoren nicht weitergereicht werden. Ein CLI-Aufruf ohne nötige
Datenbank kann keinen grünen Online-Nachweis erzeugen.

Die erste YAML-Zusammenführung hatte einen Einrückungsfehler im entfernten
Core-PostgreSQL-Block. Die tatsächliche Parserfehlermeldung bleibt erhalten;
aktuell ist die komplette YAML-Struktur erfolgreich geparst. Ein zusätzlicher
Vergleich bestätigt alle unveränderten Jobs, ursprünglichen kommerziellen
Prüfbefehle, identische Runtimebefehle und fehlende Fehlerunterdrückung.

25 tatsächliche MFA-/HTTP-/Offlinefälle aus zwei ausgewählten Originalmodulen
bestehen über den neuen Runner.1.041 vollständige Browsermodulfälle bestehen
mit null Fehlern oder Skips.19 native Paketfälle bestehen nach Herstellung der
vorhandenen lokalen Backend-Umgebung; zwei Quelleninventarfälle bestehen,
153 gepinnte Komponenten bleiben bytegleich inventarisiert. Der erste Paketlauf
hatte genau einen fehlenden lokalen venv-Pfad und bleibt als Fehlernachweis
erhalten. Kein Produktwächter wurde dafür gelockert.

Alle sechs vollständigen lokalen Browsergruppen laufen noch. Der erste Start
der eigenen PostgreSQL-Instanz scheiterte an erschöpftem temporärem Speicher;
es wurden ausschließlich eigene ignorierte, regenerierbare Flutter-Builds aus
abgeschlossenen Prüfläufen entfernt. Danach läuft dieselbe anhand voller ID,
Aufgabenlabel und Loopback-Port32798 bestätigte eigene Instanz. Fremde Container
bleiben unverändert. Abschluss, Rohbelege und spätere eigene Remote-CI werden
getrennt ergänzt. Noch keine neue Veröffentlichung oder Serverinstallation.


## Zusätzlich tatsächlich eingegrenzte Prüfprobleme

Der Materialrückgabe-Test wartete nach Freigabe einer echten verspäteten
HTTP-Antwort unbegrenzt auf Playwright response.finished(). Der eigene genaue
Prüfprozess wurde angehalten; dieser Originalversuch bleibt unvollständig/rot.
Die transparente Beobachtung des tatsächlichen OfficeApi.get-Ergebnisses
bestätigt jetzt innerhalb einer festen Frist das wirklich gelesene ursprüngliche
Entnahmeobjekt und unveränderten Ersatzdialog. Requests, Antworten und sämtliche
Bestands-/Preis-/Rechte-/Wiederholungsprüfungen bleiben erhalten. Der tatsächliche
gezielte korrigierte Ablauf besteht. Die Jahresarchiv-V2-Beobachtung bekommt
zusätzlich begrenzte echte Antwortgates mit vollständiger Freigabe im Fehlerpfad;
sein isolierter echter ZIP-/Prüfer-/Rechte-/Lifecycleablauf besteht ebenfalls.
Ein versuchter Eigentumscheck fand die alte Gruppe bereits als Zombieprozess;
es wurde dort kein Prozess beendet und kein Abschluss daraus abgeleitet.

Ein anschließend in derselben gebrauchten PG-Fixture gestarteter Runtimefall
wurde korrekt durch die feste abweichende Firmenbindung abgewiesen. Das ist
kein Grund, den Produktwächter zu lockern. Die CI-Runtime erhält stattdessen
ihren eigenen PostgreSQL-Dienst. Genau der unveränderte echte HTTPS-/MFA-/PDF-/
Worker-Neustartfall und TLS-Gatefall bestehen auf der separaten frischen eigenen
Instanz in17,277s und2,263s. Drei echte PG-/Restorefälle über den Gruppenläufer
bestehen davor in39,748s. Beide eigenen PG-Instanzen wurden danach mit voller
ID, Aufgabenlabel und Loopback-Port erneut geprüft und entfernt.

Acht Auswahl-/Fehler-/Prozessverträge bestehen einschließlich eines tatsächlich
zeitüberschrittenen Kindes: Status124 bleibt rot, die spätere Prüfung wird
wirklich ausgeführt. Jeder echte Einzelaufruf bekommt45 Minuten Obergrenze und
nur seine eigene Prozessgruppe wird bei Überschreitung beendet. Dies hebt
keinen internen Fach-/Netzwerk-/Datenbanktimeout auf.

Die lokalen Browsergruppen1,2,3 und5 sind jeweils vollständig mit13 Fällen
erfolgreich. Die ursprüngliche lange Werkzeugsitzung für Gruppe0 endete ohne
abschließenden Nachweis; sie gilt nicht als Erfolg. Die vollständige Gruppe0
läuft jetzt in einem eigenen dauerhaft protokollierten Prozess. Die betroffene
Gruppe4 wird vollständig mit ihren13 Fällen wiederholt. Die Originalberichte
und ihre Teilstände werden getrennt von Wiederholungen erhalten. Eine gesamte
78er-Browserabnahme wird erst nach tatsächlichem Abschluss ausgewiesen.
