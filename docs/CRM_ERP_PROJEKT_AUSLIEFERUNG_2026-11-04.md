# Windows- und iPhone-Auslieferung: Bestandsprüfung

Geprüft am 04.11.2026 um 19:25 UTC auf
`c875ea5a221e5d38533bb7d50a1d96b9c455d22f`.
Die Nutzerpriorität sind Projekte, Angebote, Rechnungen und Stundenaufnahme in
Browser, Windows-App und mobiler App. Lohn und Buchhaltung sind zurückgestellt.
Diese Prüfung bewertet nur Bereitstellung und vorhandene Nachweise.

**Der aktuelle lokale Stand hat noch kein passendes Windows-/iPhone-Paket.**
GitHub kennt den Commit nicht; die Abfrage aller Workflowereignisse für diese SHA
liefert null Läufe. Ältere Windows- und signierte iPhone-Artefakte sind noch
abrufbar. Sie belegen den vorhandenen Buildweg, aber nicht die neuen Funktionen.
Für einen Kundentest morgen ist damit noch keine Zusage möglich.

## Vorhandene Pakete und Zugriff

| Stand | Konkreter Nachweis | Bedeutung |
|---|---|---|
| Lokal: `0.12.0+120` / `c875ea5` | [Appversion](../app/pubspec.yaml), [sichtbare Version](../app/lib/app_version.dart) | Keine EXE, MSI, IPA oder native App im geprüften Quellbaum gefunden. Die beiden ZIPs in `downloads/` enthalten keine App-EXE. |
| Windows: `0.12.2+122` / `6371da1` | [Erfolgreicher Lauf 40222007356](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/40222007356), 25.10.2026 | `Smartplan-Office-Windows-Online-Pilot` (18.784.650 Bytes) und `Smartplan-Office-Windows` (32.166.074 Bytes), laut GitHub nicht abgelaufen; Ablauf 08.11.2026. |
| iPhone: `0.5.1`, CI-Build 110 / `f335361` | [Erfolgreicher manueller Lauf 39912954437](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/39912954437), 23.10.2026 | IPA-Export und TestFlight-Upload erfolgreich; `Smartplan-Office-iOS-110` (21.193.676 Bytes), Artefaktablauf 06.11.2026. Das daneben vorhandene `UNSIGNED`-Artefakt ist nicht installierbar. |

Die entfernten ZIPs wurden nicht heruntergeladen oder inhaltlich geprüft.
Artefaktgrößen, Ablaufdaten, Jobs und Quellversionen stammen aus aktuellen
GitHub-Leseabfragen. Der vollständige Umfang der lokalen Dateisuche ist im
[Prüfmanifest](evidence/project-release-readiness-2026-11-04/manifest.json)
festgehalten; Abhängigkeits-, Test- und Nachweisverzeichnisse waren ausgeschlossen.

`origin` zeigt auf das öffentliche Repository
`smartplanhofmann-spec/Smarplan-Hofmann-Workspace`.
Der entfernte Standardbranch `codex/smartplan-office-0.2` steht auf `3469813`;
dieser Commit ist ein Vorfahr des geprüften lokalen Stands.
Die Windows-Artefakte stammen dagegen aus dem noch **offenen, ungemergten**
[PR 8](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/pull/8)
mit Projekt-/Rücknavigation (`fix/project-feature-navigation` gegen
`fix/workspace-return-navigation`). Dessen Commit liegt lokal nicht vor.
Vor einem Release müssen diese parallelen Änderungen und die Versionsfolge
bewusst abgeglichen werden. Die größere Versionsnummer allein belegt keinen
vollständigeren Projektumfang.

Die normale Prüfung `gh auth status` meldet einen ungültigen `GH_TOKEN`.
Der vorhandene GitHub-Connector funktioniert dagegen und meldet Lese-, Schreib-
und Administrationsrechte für dieses Repository. Die Bereitstellung ist daher
nicht pauschal durch fehlenden GitHub-Zugang blockiert. Unter den vorhandenen
Connectorwerkzeugen wurde kein Workflow-Dispatch gefunden; neue Läufe können
später über die GitHub-Oberfläche bzw. eine funktionierende normale CLI-Anmeldung
gestartet werden. Es wurden keine Geheimnisdateien gelesen oder Token ausgegeben.

## Unterstützte Build- und Startwege

Für Windows baut [checks.yml](../.github/workflows/checks.yml) auf
`windows-latest` mit Flutter 3.47.7, Visual-C++-x64-/ATL-Werkzeugen und Python 3.12.
Der Workflow prüft Backend, native PDF-Verarbeitung, App-/Backend-Verbindung,
Windows-Start/Sicherung, Paketinhalt und anschließend getrennte lokale und
Online-Builds. Befehle sind `flutter build windows --release` sowie derselbe
Befehl mit `--dart-define=API_URL=https://office.smartplan-hofmann.de`
und `--dart-define=API_VERSION=v1` für die Online-App.

Für den gewünschten gemeinsamen Projektstand einschließlich Rechnungserstellung
ist das **Windows-Online-Paket** der passende vorhandene Weg: vollständig in
einen neuen Ordner entpacken, `smartplan_office.exe` öffnen, bestehendes getrenntes
Onlinekonto mit MFA verwenden. Kein lokales Python und kein SSH-Tunnel sind zum
Start nötig. Es setzt einen kompatiblen Server voraus. Es bleibt ein unsigniertes
Prüfpaket; SmartScreen und reale Gerätefunktionen müssen am Zielgerät geprüft werden.

Das lokale Windows-Paket verwendet `http://127.0.0.1:8765`, eine bereits
eingerichtete private Python-3.12-Umgebung und vorhandene lokale Konten/Daten.
Der Offline-Updater benötigt die vollständigen mitgelieferten Wheels;
`Starten.cmd` startet anschließend Server und App. Die Support-ZIPs allein
ersetzen die EXE nicht. Eigene Rechnungsausstellung ist in diesem lokalen
SQLite-Modus gesperrt; siehe [Startanleitung](../windows/START_HIER.txt).

Für iPhone/iPad verwendet [ios-testflight.yml](../.github/workflows/ios-testflight.yml)
`macos-latest`, Flutter 3.47.7 und Xcode. Die App hat Bundle-ID
`de.smartplanhofmann.office`, unterstützt iOS ab 15.0 und verbindet sich ebenfalls
mit dem bestehenden HTTPS-Server. Der automatische unsignierte Release und der
Simulator-Build sind Prüfungen, keine Geräteinstallation. Der signierte Weg
archiviert unsigniert und exportiert die IPA mit automatischer Signierung.
Nur ein ausdrücklich gewählter manueller Lauf auf
`codex/smartplan-office-0.2` mit `upload_to_testflight=true` führt zum Upload.
Die Buildnummer muss mindestens die Quell-Buildnummer erreichen und über bereits
hochgeladenen Builds liegen.

Apple-Mitgliedschaft, App-ID, Signierweg und frühere echte TestFlight-Installation
sind bereits dokumentiert; eine Neubestellung ist nicht nötig. Der Workflow
verwendet die vier vorhandenen Secret-Namen `APP_STORE_CONNECT_KEY_ID`,
`APP_STORE_CONNECT_ISSUER_ID`, `APP_STORE_CONNECT_PRIVATE_KEY`, `APPLE_TEAM_ID`.
Aktuelle Schlüsselgültigkeit, App-Store-Connect-Eintrag und installierte Geräteversion
wurden nicht geprüft. Nach einem neuen erfolgreichen Upload folgen Apples
Verarbeitung, gegebenenfalls Zuordnung zur vorhandenen Gruppe „Smartplan intern“
und das Geräteupdate; siehe [TestFlight-Anleitung](../IPHONE_TESTFLIGHT.md).

Diese Cloud läuft unter Linux. Ein Flutter-SDK liegt unter
`/workspace/toolchains/flutter`, aber Xcode, Codesign und eine Windows-
Buildumgebung sind hier nicht vorhanden. Der unterstützte Weg für neue native
Pakete sind die bereits eingerichteten Windows-/macOS-CI-Runner.

## Nächste konkrete Schritte und Grenzen

1. Den fertigen Projektumfang zu einem eindeutigen Release-Commit zusammenführen;
   offene Remote-Navigationsänderungen und Versionsnummern abgleichen. Der lokale
   Stand darf nicht als bereits auf GitHub gebaut behandelt werden.
2. Diesen Commit über den vorhandenen Repositoryzugang bereitstellen und genau
   dafür die nativen Prüfungen ausführen. Windows-Online-ZIP mit zugehörigem
   `RELEASE_MANIFEST.json` und SHA-Nachweis verwenden; keine Artefakte verschiedener
   Quellstände mischen.
3. Den tatsächlich installierten Serverstand prüfen. Für das Paket 0.12 werden
   Backend 0.12, physisches Schema 7 und `business_suite` erwartet. Ein Appupdate
   aktualisiert den Server nicht. Der vorbereitete
   [Serverupdateweg](BETRIEB_BUSINESS_UPDATE.md) hat Sicherungs-, Kandidaten- und
   Integritätsprüfungen. Es wurde hier weder verbunden noch ausgerollt.
4. Den bestehenden TestFlight-Weg für denselben Quellstand nutzen, anschließend
   Windows/iPhone tatsächlich aktualisieren und mit synthetischen Daten testen:
   dasselbe Projekt öffnen, Stunden erfassen, wiederöffnen/synchronisieren,
   Angebot/angenommenen Auftrag und Rechnungsentwurf im gleichen Projekt prüfen.
   Für echte Rechnungsausstellung bleiben dokumentierter Ausstellerwechsel und
   Nummern-/Originalprüfung erforderlich; Sevdesk wird nicht durch ein Appupdate
   automatisch abgelöst.
5. Mit den Zielgeräten insbesondere Zeitaufnahme, Flugmodus/Neustart bei nativer
   Offlinearbeit, Rückkehr zur Projektansicht und identischen Serverstand prüfen.
   Browser besitzt keine dauerhafte Offlinewarteschlange. Aktuelle installierte
   Windows-/iPhone-Version, Serverversion und Nutzerzugänge sind noch nicht belegt.

Als reine Bereitstellungsplanung **nach fertigem, geprüftem Quellstand** sind etwa
1–3 Stunden für Abgleich, grüne native Builds, Artefaktprüfung und Windows-Probe
sowie weitere 30–90 Minuten für einen problemlos durchlaufenden bestehenden
TestFlight-Weg mit Geräteprobe ein Arbeitskorridor. CI-Wartezeit, neue Buildfehler,
Serverupdate und Apples Verarbeitung können ihn verlängern. Der Korridor ist
keine Restzeit der noch ausstehenden Produktentwicklung und keine Terminzusage.

In dieser Aufgabe wurden keine Produktdateien geändert, Builds gestartet,
Artefakte installiert, Nachrichten versandt oder öffentliche Systeme verändert.
Der ursprüngliche Arbeitsbaum blieb sauber auf `c875ea5`.
