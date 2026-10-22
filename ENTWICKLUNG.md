# Smartplan Office 0.4.0 – Entwicklung und Abnahme

Version 0.4.0 ergänzt Kundenstammdaten und Projektzuordnung im lokalen Betrieb.
Vorhandene Datenbanken werden additiv auf Schema 1 erweitert; der Starter erstellt
vorher eine Sicherung. Projekt-IDs, Konten und bestehende Berichte/PDFs bleiben
erhalten. Siehe [KUNDENVERWALTUNG.md](KUNDENVERWALTUNG.md). Die Backend-Suite umfasst
32 Fälle (ein Windows-spezifischer Fall wird auf Linux übersprungen), die App-Suite
23 Tests. Nach der lokalen Stufe hat der Nutzer Hetzner als Hosting-Anbieter
gewählt und einen CAX11-Testserver in Nürnberg eingerichtet. Der bisherige
Backend-Testlauf ist auch dort bestätigt (31 bestanden, ein Windows-Fall übersprungen).
Der private systemd-Pilot, Windows-Zugriff, Fachablauf, Sicherungsdienst und
Datenzugriff nach VM-Neustart sind bestätigt; öffentliche Bereitstellung steht aus;
siehe [HETZNER_START.md](HETZNER_START.md).

Version 0.3.0 gestaltet Anmeldung, Projektübersicht, Dokumente, Teamverwaltung,
Projektzugriff und Ablage neu. Die Projektsuche, alphabetische Sortierung und
Listen-/Kachelansicht arbeiten auf den freigegebenen Projekten. Die mitgelieferte
Schrift Inter benötigt keinen externen Abruf. Siehe [DESIGN.md](DESIGN.md) für
Ansichten, Tests und die Aktualisierung der Windows-App. Der lokale Backend-Stand
0.2.0-development bleibt kompatibel; vorhandene Daten und Konten benötigen keine
Migration. Die Geschäftslogik für Freigaben und Unterschriften bleibt erhalten.

Ergänzung vom 20. Oktober 2026: [Start und Datensicherung unter Windows](WINDOWS_START_UND_SICHERUNG.md)
beschreibt den neuen gemeinsamen Start per `Starten.cmd`, automatische
Sicherungen und Wiederherstellung ohne Überschreiben vorhandener Daten.
Für den bereits eingerichteten Windows-PC ist dies der bevorzugte Startweg.
Das Start-/Sicherungsverfahren ist auch für die neue Kundendatenbank eingerichtet.

Version 0.2.1 korrigiert die JSON-Übertragung der App: POST-Anfragen enthalten
eine feste Content-Length anhand der tatsächlich gesendeten UTF-8-Bytes. Damit
kann auch der lokale Python-Server die Anfrage lesen; bei der ursprünglichen
Übertragung mit Chunked-Encoding lehnte er sie als leer ab. Der vorhandene
Backend-Stand 0.2.0 bleibt kompatibel und benötigt für diese Korrektur kein Update.

Zusätzlich zu den Oberflächen- und Transporttests wird der Dart-Client gegen
einen echten Python-Server mit temporärer Datenbank geprüft: Anmeldung,
Benutzeranlage, Projektzuweisung, Bericht mit Umlauten, Unterschrift, PDF,
Entzug des Projektzugriffs und Abmeldung. Die CI richtet dafür Python auch im
Flutter-Job und auf dem Windows-Buildrechner ein.

## Quellpaket herunterladen

Auf GitHub das Repository `smartplanhofmann-spec/Smarplan-Hofmann-Workspace`
öffnen und den Branch `codex/smartplan-office-0.2` auswählen.
Über **Code → Download ZIP** herunterladen und unter Windows entpacken.
Das Paket enthält Quellcode und Startanleitungen; eine fertige EXE mit Installer
ist noch nicht enthalten.

## Was umgesetzt ist

Die gelieferten Quellen liegen jetzt im vorgesehenen Repository. Die Anwendung ergänzt Benutzeranlage, Rollen-/Zugangsbearbeitung und Passwortwechsel für die Geschäftsführung; Projektzugriff kann zugeordnet und entfernt werden. Sitzungen werden bei Passwortwechsel, Rollenwechsel oder Sperrung beendet. Eine Anmeldung mit alten Sitzungen wird nach Reaktivierung nicht wieder gültig.

Die App listet vorhandene Berichte und Lieferscheine und öffnet Entwürfe erneut. Buchhaltung kann lesen und PDFs abrufen, aber keine Berichte erstellen oder unterschreiben. Eine Unterschrift benötigt Name, gezeichneten Verlauf und Inhaltsbestätigung. Bereits unterzeichnete Dokumente werden nicht geändert; aus ihrem Inhalt kann ein neuer Entwurf angelegt werden.

PDFs werden mit Anmeldung binär geladen, in der App angezeigt und unter Windows über einen Dateidialog gespeichert. Auf iOS erfolgt die Ausgabe über das Teilen-Menü, beispielsweise in Dateien. Fehler beim Abrufen und Ausgeben werden angezeigt. Die OneDrive-Startseite unterscheidet fehlende Einrichtung von gespeicherter Anmeldung; eine gespeicherte Anmeldung ist kein Nachweis einer aktuell funktionierenden Microsoft-Verbindung.

## Voraussetzungen

- Backend: Python 3.11 oder neuer; in der Cloud getestet mit Python 3.12.14.
- App: Flutter 3.47.7 / Dart 3.13.5. Abhängigkeiten sind in `app/pubspec.lock` festgehalten.
- Windows: Flutter-Windows-Unterstützung und Visual Studio mit Desktopentwicklung für C++; diese Voraussetzung lässt sich nicht durch Linux-Tests ersetzen.
- iPhone: macOS mit geeigneter Xcode-Version, iPhone oder Simulator; für Geräteinstallation passende Apple-Signierung. Die generierte Kennung `com.example.smartplanOffice` ist vor Verteilung durch eine eigene Bundle-ID zu ersetzen.
- Echte iPhone-Nutzung benötigt ein gemeinsam erreichbares HTTPS-Backend. Die lokale Windows-Adresse auf dem iPhone verweist auf das iPhone selbst. Das lokale Entwicklungsbackend wird nicht öffentlich freigegeben.

## Cloud einrichten und prüfen

Im vorhandenen Checkout:

```bash
cd /workspace/Smarplan-Hofmann-Workspace
bash scripts/setup-cloud.sh
```

Das Skript installiert die festgehaltenen Python-Abhängigkeiten, verwendet die geprüfte Flutter-Revision und führt Backend-Tests, Flutter-Analyse und Flutter-Tests aus. Es setzt Flutter-Konfiguration, Paketcache und Analyzer-Cache auf beschreibbare Pfade in `/workspace/toolchains`, ohne `HOME` umzusetzen. Für Flutter-Artefakte ist `storage.googleapis.com` zusätzlich zu GitHub und den Paketregistries erforderlich.

Für einzelne Flutter-Befehle in dieser Cloud:

```bash
export FLUTTER_SUPPRESS_ANALYTICS=true
export XDG_CONFIG_HOME=/workspace/toolchains/config
export ANALYZER_STATE_LOCATION_OVERRIDE=/workspace/toolchains/analyzer-cache
export PUB_CACHE=/workspace/toolchains/pub-cache
cd /workspace/Smarplan-Hofmann-Workspace/app
/workspace/toolchains/flutter/bin/flutter analyze
/workspace/toolchains/flutter/bin/flutter test
```

## Backend auf Windows

Bei Verbindungszeitlimits zu `pypi.org` kann das geprüfte Paket unter
`downloads/Smartplan_Windows_Python312_Offline.zip` verwendet werden.
Siehe [OFFLINE_INSTALLATION.md](OFFLINE_INSTALLATION.md). Es installiert die
Backend-Abhängigkeiten für Windows x64 / Python 3.12 ohne Zugriff auf PyPI.

PowerShell im Repository:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m unittest discover -v
.\.venv\Scripts\python.exe server.py --init-owner deine-email@example.de
.\.venv\Scripts\python.exe server.py
```

Den Initialisierungsschritt nur für eine neue Datenbank ausführen. Das Passwort wird verdeckt eingegeben; es gibt kein ausgeliefertes Standardkonto. `OFFICE_DATA_DIR` bestimmt den Datenordner; ohne diese Variable verwendet das Backend `backend/data`, sofern der Start aus `backend` erfolgt. Derselbe Datenordner muss für Initialisierung und Serverstart verwendet werden. Der lokale Server lauscht ausschließlich auf Loopback.

## Windows-App

### Vorgebautes Windows-Paket

Die GitHub-Prüfungen erstellen jetzt auch ein Windows-Releasepaket. Nach einem
erfolgreichen Lauf im GitHub-Reiter **Actions** den entsprechenden Lauf von
**Development checks** öffnen und unter **Artifacts** das Paket
**Smartplan-Office-Windows** herunterladen. Ein angemeldetes GitHub-Konto kann
für den Artifact-Download erforderlich sein; die Aufbewahrung beträgt 14 Tage.

Das ZIP vollständig entpacken und alle DLLs sowie den `data`-Ordner zusammen
lassen. Bei gestartetem lokalem Backend auf Port 8765 `smartplan_office.exe`
doppelt anklicken und mit dem selbst angelegten Konto anmelden. Die enthaltenen
Visual-C++-Laufzeit-DLLs ermöglichen den Start ohne Installation der
C++-Buildwerkzeuge. Python und die Backend-Abhängigkeiten werden weiterhin für
den lokalen Server benötigt. Es handelt sich um ein Testpaket ohne Installer
oder Codesignatur; der tatsächliche Start, die Anmeldung und die PDF-Funktionen
werden auf dem Windows-PC abgenommen.

Für die bereits außerhalb von OneDrive eingerichtete Python-Umgebung den
Server aus dem Quellordner mit `app` und `backend` starten:

```powershell
$env:OFFICE_DATA_DIR = "$env:LOCALAPPDATA\SmartplanOffice\data"
& "$env:LOCALAPPDATA\SmartplanOffice\.venv\Scripts\python.exe" .\backend\server.py
```

Das Serverterminal bleibt während der App-Nutzung geöffnet. Die bestehende
Datenbank und der bereits angelegte Zugang werden mit diesem Datenordner
weiterverwendet.

### Selbst bauen

In einem zweiten PowerShell-Fenster im Repository:

```powershell
cd app
flutter pub get --enforce-lockfile
flutter analyze
flutter test
flutter run -d windows
```

Die Plattformgerüste existieren bereits: `flutter create` ist nicht erneut nötig. Ein Entwicklungsbuild wird mit `flutter build windows --debug` erzeugt. Das Ergebnis muss mitsamt seinen DLLs und dem Datenordner verwendet werden; eine einzelne EXE reicht nicht. Ein Installer und signierte Updates sind noch nicht umgesetzt.

## iOS

Auf macOS aus `app` zunächst `flutter pub get --enforce-lockfile`, `flutter analyze` und `flutter test`; dann `flutter build ios --simulator --debug`. Für einen echten iPhone-Lauf das Gerät in `flutter devices` auswählen und ein geeignetes HTTPS-Testbackend übergeben:

```bash
flutter run -d <geraete-id> --dart-define=API_URL=https://<eigener-testserver>
```

Der Simulator-Build wurde in GitHub CI erfolgreich geprüft. Installation und
Nutzung auf einem echten iPhone einschließlich Signierung bleiben offen. Keine
TLS-Ausnahmen für entfernte HTTP-Server hinzufügen. Die vorhandenen
App-Icons zeigen das eigene Smartplan-Planzeichen; die Bundle-ID ist weiterhin
ein Platzhalter für die Entwicklungsphase.

## Sicherung und Wiederherstellung

Die SQLite-Sicherung funktioniert auch bei geöffneter Datenbank. Vorhandene Ziele werden nicht überschrieben:

```powershell
cd backend
.\.venv\Scripts\python.exe backup.py data\office.sqlite3 backups\office-2026-10-14.sqlite3
```

Bei `OFFICE_DATA_DIR` den entsprechenden tatsächlichen Quellpfad verwenden. Den Dateinamen für weitere Sicherungen ändern. Die Sicherung enthält Geschäftsdaten und Sitzungen, ist nicht selbst verschlüsselt und gehört in einen geschützten Speicher. Einen vorhandenen OneDrive-Tresorschlüssel getrennt sicher aufbewahren; ohne ihn können die gesicherten verschlüsselten Microsoft-Tokens nicht verwendet werden.

Zum Wiederherstellen den Server anhalten und die aktuelle Datenbank sichern. Aus `backend` die Sicherung mit `.\.venv\Scripts\python.exe restore.py backups\office-2026-10-14.sqlite3 restored-data\office.sqlite3` in einen neuen Datenordner wiederherstellen. Das Werkzeug überschreibt keine vorhandene Datei und löscht die alten Sitzungen. Anschließend `$env:OFFICE_DATA_DIR="restored-data"` setzen und den Server starten; erneut anmelden. Zunächst in einer getrennten Testinstanz prüfen. Der automatisierte Test bestätigt, dass Projekte, Anmeldung, signiertes Dokument und identische PDF-Bytes wiederhergestellt werden und alte Sitzungen gesperrt bleiben.

## Manuelle native Abnahme

1. Geschäftsführung anmelden; Benutzer mit mindestens zwölf Passwortzeichen anlegen, Projekt erstellen und Techniker zuweisen.
2. Als Techniker anmelden: nur zugewiesene Projekte sichtbar; keinen Zugriff auf Benutzerverwaltung.
3. Servicebericht erstellen, Entwurf wieder öffnen und Vorschau ansehen. Name eingeben, tatsächliche Unterschrift zeichnen und Inhalt bestätigen; anschließend speichern.
4. App neu öffnen/anmelden: unterzeichneten Bericht erneut laden; PDF ansehen und dauerhaft speichern beziehungsweise auf iOS in Dateien teilen.
5. Als Buchhaltung dieselben freigegebenen Berichte lesen; keine Unterschriften-/Erstellungsschaltflächen.
6. Technikerzugriff entfernen: ein erneuter Abruf ist gesperrt. Benutzer deaktivieren: die nächste API-Anfrage beendet die Sitzung. Bereits exportierte Dateien lassen sich dadurch nicht zurückrufen.
7. Kleinere Fenster, iPhone-Hochformat, Abbruch des Dateidialogs, unterbrochene Verbindung und fehlerhafte Anmeldung prüfen.

Die CI-Datei `.github/workflows/checks.yml` bereitet Backend-, Flutter-, Windows- und iOS-Simulatorchecks vor. Ein Push kann diese Prüfungen auslösen, sofern GitHub Actions im Repository aktiviert ist. Ergebnisse im GitHub-Reiter Actions separat prüfen; die erfolgreichen lokalen Tests belegen keinen erfolgreichen nativen CI-Build.

## Noch offen

Native Builds wurden im GitHub-Lauf `38548684395` für Windows (Debug) und den
iOS-Simulator erfolgreich abgeschlossen. Auf dem Nutzer-PC bestanden inzwischen
auch die 17 Backend-Tests sowie PDF-Erzeugung und Verschlüsselung. Das neue
Windows-Releasepaket wird durch die ergänzte CI separat geprüft.

Der Nutzer hat unter Windows inzwischen Anmeldung, Projektanlage,
Servicebericht, Unterschrift, PDF-Ausgabe, Benutzerverwaltung und Entzug des
Technikerzugriffs bestätigt. Anschließend wurden auch die neue Oberfläche,
der Starter, die manuelle Sicherung und die Wiederherstellung mit erneutem
Zugriff auf Projekte, unterschriebene Berichte und PDF bestätigt.

Der maßgebliche erfolgreiche GUI-0.3.0-Build ist GitHub-Lauf `39416338557`
(Windows-Artefakt `12261258366`). Die App-Suite umfasst 18 erfolgreiche Tests.
Die neue Kundenstufe benötigt noch eine kurze Abnahme auf dem Nutzer-PC.
Ein CAX11-Testserver mit SSH-Zugang ist inzwischen vorhanden. Der private
Loopback-Testdienst und der Windows-Ablauf einschließlich Datenzugriff nach
VM-Neustart sind bestätigt; öffentlicher gemeinsamer Gerätebetrieb
ist noch nicht freigegeben. Wix-DNS-Zugriff und der A-Eintrag für
`office.smartplan-hofmann.de` auf die VM sind am 22. Oktober bestätigt.
Das [HTTPS-Einrichtungspaket](deploy/hetzner/https/README.md) mit isolierter
statischer Seite ist lokal geprüft und auf dem Nutzer-Server installiert.
systemd-Status und öffentlicher Browseraufruf über HTTPS ohne sichtbare
Zertifikatswarnung sind per Screenshot bestätigt.
Siehe [BETRIEB_UND_IPHONE.md](BETRIEB_UND_IPHONE.md).

Die nächste Stufe 0.5 ergänzt `backend/online` mit PostgreSQL, Flask/Gunicorn und
Passwort/TOTP sowie QR-Einrichtung und Recovery-Codes in Flutter. Die
[Online-Pilot-Anleitung](deploy/hetzner/online/README.md) trennt lokale Tests,
Installation und noch offene echte Geräteabnahme. CI erzeugt zusätzlich das
separate Artefakt `Smartplan-Office-Windows-Online-Pilot` mit festem HTTPS-Host
und API-Version `v1`; das lokale Windows-Paket bleibt erhalten.

Noch offen sind tatsächliche iPhone-App-Läufe einschließlich
PDF-Vorschau, Signaturgesten und Speichern; produktive API, PostgreSQL, App-Anbindung über HTTPS und
Mehrbenutzerbetrieb; echte OneDrive-Anmeldung; CRM/Angebote/Planung;
Zeiten/Material/Offline; Buchhaltung/Banken; WhatsApp/Kalender/KI/MCP; Installer,
Signierung und Veröffentlichung. Siehe `UMSETZUNGSPLAN.md`.

Die derzeitige Implementierung ist eine lokal testbare Entwicklungsstufe, keine fertige Gesamtsoftware und kein freigegebener produktiver Betrieb.
