# Smartplan Office – Übergabe an Abacus DeepAgent

## Auftrag des Nutzers

Der Nutzer möchte mit **Abacus** weiterarbeiten und ausdrücklich eine **native
iPhone-App**. Ziel ist eine installierbare App mit der vorhandenen Flutter-
Oberfläche und gemeinsamem Datenbestand mit Windows. Der geplante erste
Verteilungsweg ist TestFlight. Die Apple-Developer-Mitgliedschaft wurde am
22. Oktober 2026 als Einzelunternehmer für 99 Euro pro Jahr bestellt; die Aktivierung
war zuletzt noch in Bearbeitung. Die Entwicklung und technischen Vorbereitungen selbständig fortsetzen;
für echte Kontozugänge ausschließlich geeignete sichere Einstellungen verwenden.
Passwörter, private SSH-Schlüssel und Apple-Signierschlüssel gehören nicht in Chats.

## Bestehendes Projekt übernehmen

- Repository: https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace
- Arbeitsbranch: `codex/smartplan-office-0.2`
- Plattformen: Flutter/Dart, Windows und natives iOS; App-Version `0.5.0+6`.
- Funktionscode des abgenommenen Online-Piloten:
  `6777fb9ee64eaf05d08cfc13be98049641b663bc`.
  Spätere Commits bis zu dieser Übergabe ergänzen Abnahmen/Planung.
- App unter `app/`, lokales Backend unter `backend/`, Online-Backend unter
  `backend/online/`, Serverinstallation unter `deploy/hetzner/`.
- Flutter **3.47.7**, Dart **3.13.5**, Python **3.12**, PostgreSQL **16**.
  Abhängigkeiten und Lockfiles sind vorhanden. GitHub Actions baut Windows
  und den iOS-Simulator; `app/ios` ist bereits erzeugt.

Die bestehende Flutter-Anwendung und API weiterverwenden. Der Nutzer hat die
native iPhone-App gewählt; eine Website/PWA ist kein Ersatz für dieses Ergebnis.
Der abgenommene Windows-Betrieb und die gespeicherten Unterschriften/PDFs bleiben
erhalten. Eine neue Backend-Plattform oder Datenbank ist für diese Aufgabe
nicht erforderlich.

## Laufender Online-Pilot

- HTTPS-Adresse: **https://office.smartplan-hofmann.de**
- API: **`/api/v1`**. Beispiel: `/api/v1/projects`.
- Native Build-Konfiguration:
  `--dart-define=API_URL=https://office.smartplan-hofmann.de --dart-define=API_VERSION=v1`.
- Das Backend ist Flask/Gunicorn mit PostgreSQL; es läuft bereits auf einer
  Hetzner-CAX11-ARM64-VM mit Ubuntu 24.04. Caddy stellt HTTPS bereit.
- Ein geöffnetes SSH-Fenster oder Tunnel ist für die Online-App nicht erforderlich.
- Keine neue Hosting-Buchung oder Umstellung des funktionierenden Servers nötig.
  Ein direkter Server-/Apple-Zugang ist im Projektpaket nicht enthalten.

### Anmeldung und Rechte

`POST /api/v1/login` mit E-Mail/Passwort liefert eine begrenzte MFA-Herausforderung.
Bei der Ersteinrichtung enthält sie `enrollment` mit Authenticator-URI/Schlüssel.
`POST /api/v1/login/verify` mit Herausforderung und Code liefert das Sitzungstoken;
bei Ersteinrichtung einmalig Wiederherstellungscodes. Fachabrufe verwenden
`Authorization: Bearer TOKEN`. Flutter implementiert diesen Ablauf bereits.
Tokens bleiben im App-Arbeitsspeicher. Es gibt kein Standardpasswort.

Vier Rollen: `owner`, `manager`, `technician`, `accountant`. Außer der
Geschäftsführung sehen Nutzer ausschließlich zugewiesene Projekte. Kundenkontakte
und interne Notizen sind der Geschäftsführung vorbehalten. Rechte gelten auch
für PDF-Abrufe; signierte Berichte sind unveränderlich. Ein neuer Testnutzer
wird über die vorhandene Benutzerverwaltung angelegt und Projekten zugewiesen.

## Bereits bestätigt – keine vollständige Neueinrichtung verlangen

Der Nutzer arbeitet auf Windows und besitzt ein iPhone, aber keinen Mac.
Unter Windows sind Online-Anmeldung, fiktiver Kunde, Projekt, Servicebericht,
Unterschrift und PDF bestätigt. SSH war bereits vor dem Start der App geschlossen.
Nach einem geordneten vollständigen VM-Neustart waren Projekt und PDF erneut
zugänglich. Echte lokale Windows-Daten wurden noch nicht auf den Server übernommen.

Technische Nachweise des Online-Standes:

- 32 bisherige Backend-Fälle unter Linux: ein Windows-spezifischer Skip.
- 19 PostgreSQL-/MFA-Fälle, darunter Rechteentzug, konkurrierende Unterschriften,
  Verbindungsverlust und echte Dump-/Restore-Prüfung mit identischem PDF.
- Echter Caddy/Gunicorn/PostgreSQL-Test über verifiziertes TLS mit Test-CA,
  MFA, PDF und API-Neustart.
- Flutter-Analyse und 27 App-Tests bestanden.
- GitHub-Lauf https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/39835146915
  insgesamt erfolgreich, einschließlich Windows und iOS-Simulator.

Ein erfolgreicher Simulator-Build ist noch keine Geräteinstallation.
Die genauen manuellen Nachweise stehen in `deploy/hetzner/ABNAHME.md`.

## Konkrete nächste Arbeit: native iPhone-App

1. Vorhandenes Flutter-iOS-Projekt prüfen. Die Bundle-ID ist derzeit noch
   `com.example.smartplanOffice`; eine eigene ID auf Basis der kontrollierten
   Domain `smartplan-hofmann.de` festlegen und mit dem Apple-Konto abgleichen.
2. Online-Konfiguration für Geräte- und Simulator-Builds setzen. Der bisherige
   generische Simulator-Job baut noch mit der lokalen Standardadresse;
   auf dem iPhone muss die obige HTTPS-/API-v1-Konfiguration verwendet werden.
3. Apple-Team, App-ID, Distribution-Zertifikat und App-Store-Connect-Profil
   prüfen und die sichere Signierung auf einem macOS-CI-Runner vorbereiten.
   Der Nutzer hat keinen lokalen Mac. Die Apple-Mitgliedschaft ist bestellt;
   ihre Freischaltung und die Bereitstellung der Apple-Signierzugänge stehen noch aus.
4. Zuerst lauffähigen Simulator-/Gerätebuild und passende Release-Prüfungen
   herstellen. Danach das signierte TestFlight-Paket mit den tatsächlich
   bereitgestellten Apple-Zugängen erstellen und auf dem Nutzer-iPhone testen.
5. Mit fiktiven Daten prüfen: Windows legt ein Projekt an, ein zugewiesener
   iPhone-Nutzer öffnet es, erstellt und unterschreibt einen Bericht; Windows
   öffnet dasselbe PDF. Projektentzug sperrt weitere Abrufe. PDF-Teilen,
   Signaturgesten und erneute Anmeldung auf echtem iOS abnehmen.

Eine neue kostenpflichtige Apple-Mitgliedschaft, ein Signierdienst oder andere
Abos werden erst nach konkreter Preis-/Leistungsfreigabe gebucht. Vorhandene
Zugänge über sichere Anbieter-/CI-Einstellungen bereitstellen, nicht im Chat.
Ein iPhone, das seinen eigenen Authenticator zur Anmeldung nutzt, benötigt eine
praktische Ersteinrichtung über den manuellen Schlüssel bzw. ein zweites Gerät.

## Offene Aufgaben erhalten

- **Nächstes Windows-Update:** Der Nutzer sah SmartScreen und verlangte eine
  Verbesserung. Aktuelle Testpakete sind unsigniert. Vertrauenswürdige Windows-
  Codesignierung, Herausgeber/Zeitstempel, signiertes Installationspaket und
  Prüfung des tatsächlichen Downloads sind vorgezogen. Zertifikat/Signierdienst
  und Kosten sind noch nicht ausgewählt. Eine Signatur allein garantiert keine
  sofortige SmartScreen-Reputation.
- Eigene native iPhone-App samt Signierung und Geräteabnahme ist noch offen.
- OneDrive Personal/Family: vorbereitet, aber noch kein echtes Microsoft-Konto
  verbunden; Online-API meldet es derzeit bewusst als unkonfiguriert.
- Übernahme echter Daten aus einer geprüften SQLite-Sicherung bleibt ein
  eigener Migrations-/Abnahmeschritt.
- Lokale PostgreSQL-Dumps und Hetzner-Backups sind vorhanden. Getrennte
  verschlüsselte Sicherung, sichere Sicherung des Vault-Schlüssels,
  Aufbewahrung/Benachrichtigung und Betriebszuständigkeit bleiben offen.
- Weitere Fachmodule bleiben im `UMSETZUNGSPLAN.md`; diese Übergabe soll zuerst
  den gemeinsamen nativen Windows-/iPhone-Ablauf fertigstellen.

## Nützliche Dateien

`README.md`, `ENTWICKLUNG.md`, `BETRIEB_UND_IPHONE.md`, `UMSETZUNGSPLAN.md`,
`deploy/hetzner/ABNAHME.md`, `deploy/hetzner/online/README.md`,
`.github/workflows/checks.yml`, `app/lib/api.dart`, `app/lib/mfa_dialog.dart`,
`app/lib/project_page.dart`, `app/lib/pdf_page.dart`.

Das Übergabepaket enthält verfolgte Projektdateien. Laufende Datenbanken,
Benutzerpasswörter, private SSH-/Apple-Schlüssel, virtuelle Umgebungen und
lokale Buildverzeichnisse gehören nicht in das Paket.

## iPhone über TestFlight
Schritt-für-Schritt-Anleitung ohne Mac: siehe [IPHONE_TESTFLIGHT.md](IPHONE_TESTFLIGHT.md) (Workflow `.github/workflows/ios-testflight.yml`).
