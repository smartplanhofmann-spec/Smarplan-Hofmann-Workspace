# Smartplan Office 0.2 – Entwicklung und Abnahme

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

Dies sind native Abnahmeschritte; ihr Erfolg wurde in der Linux-Cloud nicht bestätigt. Keine TLS-Ausnahmen für entfernte HTTP-Server hinzufügen. Die vorhandenen Standard-App-Icons und die Bundle-ID sind Platzhalter für die Entwicklungsphase.

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

Native Builds und Tests auf Windows/iPhone einschließlich PDF-Plugin, Signaturgesten und Speichern; produktive API, PostgreSQL, HTTPS und Mehrbenutzerbetrieb; echte OneDrive-Anmeldung; CRM/Angebote/Planung; Zeiten/Material/Offline; Buchhaltung/Banken; WhatsApp/Kalender/KI/MCP; Installer, Signierung und Veröffentlichung. Siehe `UMSETZUNGSPLAN.md`.

Die derzeitige Implementierung ist eine lokal testbare Entwicklungsstufe, keine fertige Gesamtsoftware und kein freigegebener produktiver Betrieb.
