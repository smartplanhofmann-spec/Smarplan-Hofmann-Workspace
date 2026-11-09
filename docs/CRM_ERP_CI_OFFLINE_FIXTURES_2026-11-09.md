# Offline-Testaufbauten für die neue Firmenbindung

Der erste neue CI-Lauf auf 8273852 bestätigt zwei Fehler in Testaufbauten.
Diese Korrektur verändert ausschließlich Tests und Nachweise. Firmenbindung,
Dateischutz und Berechtigungsprüfung des Produkts bleiben unverändert.

## Gebundene Finanztests

Der Online-API-Job 129288305481 in Development42654230472 scheitert an
`test_accounting_http`: Die gebundene Testfirma versucht einen neuen V1-Zugang
anzulegen und erwartet 201. Die Anwendung verweigert diesen alten Vertrag
korrekt mit 409. Sieben vorhandene Finanz-Grenzfälle verwenden denselben
veralteten Aufbau; außerdem betrifft es einen unternehmensweiten Ereignistest.

Die Tests beantragen jetzt ausdrücklich V2 und senden die tatsächliche
Firmen-/Kontobindung. Vor der Finanzsperre wird eine erlaubte Anfrage desselben
Zugangs erfolgreich ausgeführt. Ein Workspacezugang darf Projekte lesen;
Business-Capabilities sind für ihn bereits gesperrt. Der erste ergänzte
Positivnachweis wählte fälschlich diesen Businesspfad und scheiterte deshalb
in sieben Fällen. Ein zusätzlicher echter HTTP-Abgleich belegt die korrekte
Abgrenzung: Projekte 200, Business-Capabilities 403, Buchhaltung 403.
Dieser Zwischenfehler bleibt archiviert; der endgültige Positivnachweis
verwendet den erlaubten Projektpfad.

Damit kann eine fehlende Bindung nicht versehentlich als bestandener
Finanzrechttest zählen. Ungebundene V1-Kompatibilitätstests und die explizite
V1-Ablehnung gebundener Firmen werden nicht pauschal umgeschrieben.

## Windows und der eingebettete Server

Der Windows-Job 129288306410 scheitert beim Import von `fcntl`: Ein zuvor
portabler Clienttest provisioniert inzwischen einen echten POSIX-Onlineserver
mit `flock`, `openat` und privatem Storage-Marker. Diese Serverfunktionen
gehören nicht zum Windowsclient und werden nicht nachgebaut oder abgeschaltet.

Die Testdatei enthält nun zwei tatsächliche HTTP-Fälle:

- Der portable lokale Server bestätigt keine Firmenbindung. Der Client muss
  neue Offlinearbeit ablehnen, eine vorhandene Testdatei unverändert erhalten
  und keine Schlüssel, gespeicherten Sitzungen oder Kontozuordnung erzeugen.
  Die bestehende Onlineanmeldung und Projektansicht bleiben nutzbar.
- Der tatsächlich provisionierte POSIX-V2-Server prüft weiterhin verschlüsselten
  App-Neustart, identischen ursprünglichen Plan, Synchronisation ohne Dublette
  und Geräteberechtigung. Nur dieser Serverfall trägt den bestehenden Tag
  `posix_backend`; die Windows-CI-Auswahl behält den portablen HTTP-Fall.

Ein erster Split erwartete versehentlich neue Offlinearbeit am ungebundenen
Server. Der Client verweigerte sie korrekt. Der Fehlversuch bleibt erhalten;
die endgültige Prüfung verlangt ausdrücklich diese Ablehnung. Es gibt keinen
Fallback auf einen unsicheren neuen V1-Cache und keine fingierte Firmenbindung.

## Tatsächliche Ergebnisse

Der unsignierte iPhone-Lauf 42654230385 ist anschließend an drei Fällen der
Service-Journal-HTTP-Datei gescheitert. Ihre temporäre Ablage wird über macOS
`/var` erreicht; der strenge POSIX-Binder verweigert diesen nicht aufgelösten
Pfadlink korrekt. Dieser Fehler ist vor Änderung mit genau dem unveränderten
Python-Testserver und einem tatsächlichen kontrollierten Pfadlink auf Linux
reproduziert. Der neue Testaufbau löst seine vorhandene Wurzel mit
`resolve(strict=True)` auf. Der erste vollständige Service-Neustart-/HTTP-/UI-
Fall läuft jetzt ausdrücklich durch einen echten temporären Pfadlink.
Die drei vollständigen Servicefälle bestehen; der produktive Binder und seine
Ablehnung von Links innerhalb der Ablage bleiben unverändert. Die anderen
eingebetteten Binder-Aufbauten sind auf denselben Fehler gegengeprüft.

| Lauf | Ergebnis |
| --- | --- |
| Acht betroffene Buchhaltungs-/Ereignismodule mit echtem MFA/HTTP | 52 bestanden, kein Fehler/Skip, 137,663 Sekunden |
| Beide tatsächlichen Offline-HTTP-Fälle | Zwei bestanden, kein Fehler/Skip |
| Windows-Tagauswahl auf Linux | Genau der eine portable Fall bestanden; kein tatsächlicher Windows-Gerätenachweis |
| Analyse der geänderten Dart-Testdatei | Kein Befund, 9,7 Sekunden |
| Vollständige Service-Journal-HTTP-Datei mit tatsächlichem Pfadlink | Drei bestanden, kein Fehler/Skip, 23 Sekunden im Fortschrittslog |
| Analyse der Service-Journal-HTTP-Datei | Kein Befund, 12,7 Sekunden |

[Rohprotokolle, Quellhashes und vollständige Metadaten](evidence/ci-offline-fixtures-2026-11-09/verification.json).
Die ursprünglichen fehlgeschlagenen GitHub-Jobs und beide Zwischenfehler sind
gesondert archiviert. Ihre Ergebnisse werden durch spätere lokale Erfolge
nicht nachträglich grün. Eine neue Remoteprüfung muss den korrigierten Stand
selbst bestätigen. Installation auf dem Kundenserver und echte Geräteabnahme
sind nicht Teil dieser Testkorrektur.
