# Smartplan Office - Entwicklungsstand 0.5.0

Neue Entwicklungsstufe: [Projektpläne](PROJEKTPLAENE.md) mit projektbezogener
Speicherung, Wandzeichnung, Versionskonfliktprüfung und verschlüsselter
[Offline-Nutzung für sieben Tage](OFFLINE_UND_SYNCHRONISIERUNG.md). Flutter-Analyse
und automatisierte Tests bestanden; Bereitstellung und Geräteprüfung stehen aus.

Version 0.5.0 bereitet den getrennten [Online-Piloten](deploy/hetzner/online/README.md)
vor: PostgreSQL, versionierte Flask/Gunicorn-API, Passwort plus Authenticator-Code,
QR-Einrichtung und Wiederherstellungscodes. CI erstellt zusätzlich das Windows-
Artefakt `Smartplan-Office-Windows-Online-Pilot` mit der festen HTTPS-Testadresse.
Die HTTPS-Seite, API-Installation und öffentliche Zugriffssperre sind auf Hetzner
bestätigt. Der Nutzer bestätigte die Windows-Online-Anmeldung und den fiktiven
Kunden-/Projekt-/Berichtsablauf mit Unterschrift/PDF ohne SSH-Fenster sowie
erneuten Datenzugriff nach VM-Neustart. Bestehende lokale Daten bleiben getrennt.
Echte Datenübernahme und iPhone-Verteilung folgen. Die SmartScreen-Warnung des
unsignierten Testpakets ist für das nächste Windows-Update zu bearbeiten.

Version 0.4.0 ergänzt eine lokale Kundenverwaltung: Kontaktdaten, Ansprechpartner,
Adressen und Notizen, Suche, Archivierung sowie die Zuordnung zu Projekten.
Bestehende Projektkunden werden übernommen; unterschriebene Berichte und PDF-Dateien
behalten ihren ursprünglichen Inhalt. Siehe [KUNDENVERWALTUNG.md](KUNDENVERWALTUNG.md).
Die bisherige Version läuft lokal. Ein Hetzner-CAX11-Testserver in Nürnberg ist
eingerichtet; auf ARM bestanden 31 Backend-Tests (ein weiterer Windows-Test
übersprungen). Der separate Online-Pilot ist inzwischen wie oben beschrieben
bereitgestellt; iPhone-Zugriff steht noch aus.
Der nächste Schritt und die Vorbereitung stehen in [HETZNER_START.md](HETZNER_START.md).

Der aktuelle Stand ergänzt Benutzerverwaltung, Projektzugriff, Berichtslisten,
PDF-Vorschau/-Speicherung und Sicherung/Wiederherstellung. Windows- und iOS-Gerüste
sind vorhanden. Geprüfte Startbefehle, Werkzeugversionen, Tests und native
Abnahmeschritte stehen in [ENTWICKLUNG.md](ENTWICKLUNG.md).
Die folgenden ursprünglichen Abschnitte beschreiben den gelieferten Stand 0.1;
für aktualisierte Einrichtung und verbleibende Einschränkungen gilt ENTWICKLUNG.md.

Ergänzung vom 20. Oktober 2026: Für den eingerichteten Windows-PC gibt es jetzt
[Start und Datensicherung](WINDOWS_START_UND_SICHERUNG.md) per Doppelklick.
Das kleine Zusatzpaket verwendet die vorhandene App und Python-Umgebung;
es sichert vor dem Start und nach dem Schließen und stellt Sicherungen in
einem neuen Datenordner wieder her.

Version 0.3.0 überarbeitet die gesamte App-Oberfläche: einheitliche Typografie,
helle Arbeitsflächen, Seitenleiste, Projektsuche und Listenansicht sowie eine
anpassungsfähige Dokument- und Unterschriftenansicht. Gerenderte Ansichten und
Hinweise zum Aktualisieren stehen in [DESIGN.md](DESIGN.md).

Individuelle Unternehmenssoftware für Smartplan Hofmann. Ziel: Windows-Desktop-App
und iPhone-App mit gemeinsamer Datenbasis, Benutzerrechten und KI-Anbindungen.
OneDrive Family bleibt für den ersten Stand vorgesehen. Ein Wechsel auf Business
und eine NAS sind ausdrücklich auf später verschoben.

## Was dieser Stand enthält

- Python-Backend mit SQLite für lokale Entwicklung, REST-Endpunkten und Anmeldung.
- Vier Rollen: Geschäftsführung (`owner`), Projektleitung (`manager`), Techniker
  (`technician`) und Buchhaltung (`accountant`). Alle außer der Geschäftsführung
  sehen ausschließlich explizit zugewiesene Projekte.
- Projektanlage, Benutzeranlage und Projektzuweisung über die API. Die App zeigt
  Projekte und bietet der Geschäftsführung die Projektanlage an.
- Serviceberichte und Lieferscheine: Entwurf, Inhaltsprüfung, zeichnerische
  Unterschrift, Unterzeichnername, Serverzeit in UTC und PDF-Erzeugung.
- Inhalts-Hash und gespeicherter PDF-Hash. Das öffentliche API bietet keine
  Bearbeitung bereits unterschriebener Berichte an. Korrekturen sind neue Entwürfe.
- Vorbereiteter OneDrive-Personal-Anschluss mit OAuth Authorization Code, PKCE,
  einmaligem State, verschlüsselten Tokens, Refresh und PDF-Upload in den App-Ordner.
- Flutter-App-Quellcode für Windows und iOS, Anmeldung, Projektübersicht,
  Berichtserstellung und Unterschriftenfeld. Das Token bleibt nur im Arbeitsspeicher.
- Neun erfolgreiche Backend-Tests, einschließlich tatsächlicher lokaler HTTP-Anfragen.

## Was noch nicht enthalten oder live geprüft ist

Keine Windows-EXE, kein Installer und keine installierbare iPhone-App. Flutter/Dart,
Windows-Buildwerkzeuge und Xcode fehlen in der Erstellungsumgebung; der Dart-Code
wurde deshalb noch nicht kompiliert oder auf Geräten getestet. Native Plattformgerüste
müssen erzeugt werden. Dies ist eine Entwicklungsgrundlage, keine produktive ERP-Lösung.

Die OneDrive-Anbindung ist mit simulierten Microsoft-Antworten getestet. Es wurde
kein Microsoft-Konto angemeldet, keine App registriert und keine echte Datei hochgeladen.
Grok Bots, MCP, WhatsApp, Banken, sevdesk, Kalender, Offline-Synchronisierung,
Zeiterfassung, Materialverwaltung und eine vollständige Kundenverwaltung folgen.
Feingranulare Einzelrechte, Benutzerverwaltung in der Oberfläche und externe Partnerrollen
sind noch nicht umgesetzt. Kein Nachweis von GoBD-Konformität oder qualifizierter
elektronischer Signatur. Direkter Zugriff auf die Datenbank oder OneDrive bleibt vom
App-Rechtesystem unabhängig und muss bei der späteren Betriebsplanung berücksichtigt werden.

## Backend lokal auf Windows starten

Python 3.11 oder neuer installieren, Projektordner in Codex öffnen. In PowerShell:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe server.py --init-owner deine-email@example.de
.\.venv\Scripts\python.exe server.py
```

Das Passwort wird verdeckt abgefragt. Es gibt kein ausgeliefertes Standardpasswort.
Der Server lauscht ausschließlich auf `127.0.0.1:8765` und ist damit nur lokal
erreichbar. Daten werden unter `backend/data` gespeichert. Der Windows-Prototyp
kann dieselbe Loopback-Adresse nutzen. Für einen iPhone-Test braucht es ein gemeinsam
erreichbares HTTPS-Backend und eine passende OAuth-Rücksprungadresse; das gehört
zur nächsten Bereitstellungsstufe. Den Entwicklungsserver nicht öffentlich freigeben.

Tests aus `backend` starten:

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_office
```

## App-Quellcode weiterbauen

Flutter mit Windows-Desktop-Unterstützung und Visual Studio C++ Build Tools
einrichten. iOS benötigt macOS, Xcode und für die Verteilung eine passende
Apple-Entwicklerkonfiguration. Zunächst eine Sicherung/Commit des gelieferten
Quellcodes erstellen. Aus `app`:

```powershell
flutter create --platforms=windows,ios --project-name smartplan_office .
flutter pub get
flutter analyze
flutter run -d windows
```

`--overwrite` nicht verwenden; `lib/main.dart` und die eigene `pubspec.yaml`
behalten. Empfohlene Ausgangsversion: Flutter 3.47. Für eine entfernte Testumgebung
`--dart-define=API_URL=https://dein-testserver.example` verwenden. Die App lehnt
unverschlüsseltes HTTP zu entfernten Servern ab. Der native Start/Build ist hier
noch unbestätigt und der erste Schritt in der lokalen Codex-Umgebung.

## OneDrive Family verbinden

Für den gemeinsamen Online-Piloten sind Projektverwaltung und Datenbank auf
Hetzner die führende Quelle. Version 0.6 ergänzt eine wählbare zusätzliche
Dokumentablage mit Projektordnern: Smartplan-Server, OneDrive oder HTTPS-WebDAV
(Cloud/NAS). Einrichtung und sichere Aktualisierung des vorhandenen Dienstes:
[Speicheranschlüsse](deploy/hetzner/online/STORAGE.md). Ein Speicherkonto wurde
dadurch noch nicht tatsächlich verbunden.

Die folgende Konfiguration betrifft den getrennten lokalen SQLite-Piloten.

Eine Microsoft-App-Registrierung anlegen, die persönliche Microsoft-Konten
unterstützt. Falls noch kein Entra-Entwicklermandant besteht, muss dieser Zugang
zuerst eingerichtet werden; das ersetzt nicht das Family-Abonnement.
Für die lokale Backend-Variante eine Web-Rücksprungadresse exakt
`http://localhost:8765/oauth/callback` registrieren, Client-ID und Secret hinterlegen.
Delegierter Scope: `Files.ReadWrite.AppFolder`, ergänzt um `offline_access`.
Der Code verwendet ausdrücklich den `consumers`-Anmeldeendpunkt, nicht
einen unbeaufsichtigten Zugriff mittels Client Credentials.

Umgebungsvariablen setzen, z.B. durch sichere Eingabe in PowerShell oder den
Secret-Mechanismus der Entwicklungsumgebung. Die Datei `.env.example` beschreibt
die Variablen; sie wird nicht automatisch eingelesen. Den Tresorschlüssel einmal
erzeugen und dauerhaft getrennt sichern:

```powershell
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

`MS_CLIENT_ID`, `MS_CLIENT_SECRET`, `MS_REDIRECT_URI` und `OFFICE_VAULT_KEY`
beim Serverstart bereitstellen. Keine echten Secrets in Quellcode, Git oder Chats.
Die Geschäftsführung öffnet in der App "OneDrive Family verbinden". Der erste
Prototyp zeigt den Anmeldelink zum Kopieren in den Browser; automatisches Öffnen
und eine Verbindungsstatusseite werden ergänzt. Microsoft-Zustimmung abschließen.
Danach kann die Geschäftsführung einen unterschriebenen Bericht nach OneDrive
hochladen. Es wird kein öffentlicher Freigabelink erstellt.

Dateien liegen unter `Apps/<Name der Microsoft-App>` mit Projekt- und Dokument-ID
im Dateinamen. Bestehende Projektordner außerhalb dieses App-Ordners werden nicht
eingelesen. Für deren spätere Übernahme braucht es einen gesonderten Import oder
eine bewusst weiter gefasste Berechtigung. Die lokale Dokumentkopie und Datenbank
sind die primäre Quelle des Prototyps; OneDrive ist die zusätzliche Ablage.

## Architektur und nächste Entwicklungsschritte

Die native Oberfläche spricht mit dem Backend. Berechtigungen und Datenzugriffe
werden dort geprüft. OneDrive ist Dokumentablage, keine synchronisierte Live-Datenbank.
Für den späteren Mehrbenutzerbetrieb: PostgreSQL, migrationsfähiges Datenmodell,
geeigneter HTTPS-Appserver, verwaltete Anmeldung/MFA, sichere mobile Ablage,
Backups und getestete Wiederherstellung. SQLite/Standardbibliothek-HTTP bleiben
Hilfsmittel der lokalen Entwicklungsstufe.

Vollständige Anforderungen und nächste Aufgaben: `CODEX_HANDOFF.md`.

## Primärquellen

- https://learn.microsoft.com/en-us/graph/onedrive-sharepoint-appfolder
- https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-auth-code-flow
- https://docs.flutter.dev/reference/supported-platforms
- https://docs.x.ai/developers/tools/remote-mcp
- https://docs.x.ai/grok-bot/team-bots
- https://developers.openai.com/api/docs/guides/tools-connectors-mcp
- https://docs.qonto.com/api-reference/business-api/transactions-statements/transactions/list-transactions

Geprüft am 14.10.2026. Konkrete Bankabdeckung und Microsoft-Appzugang sind vor
Aktivierung jeweils am tatsächlichen Konto zu prüfen.
