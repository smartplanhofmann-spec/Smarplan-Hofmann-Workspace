# Smartplan Office – Übergabe an Abacus DeepAgent

## Auftrag des Nutzers

Der Nutzer möchte mit **Abacus** weiterarbeiten und ausdrücklich eine **native
iPhone-App**. Ziel ist eine installierbare App mit der vorhandenen Flutter-
Oberfläche und gemeinsamem Datenbestand mit Windows. Der geplante erste
Verteilungsweg ist TestFlight. Die Apple-Developer-Mitgliedschaft wurde am
22. Oktober 2026 als Einzelunternehmer für 99 Euro pro Jahr bestellt. Am 23. Oktober
bestätigte der Nutzer die installierte iPhone-App nach der Meldung zu TestFlight-Build 108
und einen gemeinsamen Windows-/iPhone-Berichtsablauf. Die Entwicklung selbständig fortsetzen;
für echte Kontozugänge ausschließlich geeignete sichere Einstellungen verwenden.
Passwörter, private SSH-Schlüssel und Apple-Signierschlüssel gehören nicht in Chats.

## Bestehendes Projekt übernehmen

- Repository: https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace
- Arbeitsbranch: `codex/smartplan-office-0.2`
- Plattformen: Flutter/Dart, Windows und natives iOS; vorbereitete App-Version `0.6.0+8`.
- Funktionscode des abgenommenen Online-Piloten:
  `6777fb9ee64eaf05d08cfc13be98049641b663bc`.
  Abacus ergänzt in `6e8e37d` die iOS-Bundle-ID, Exportoptionen und Anleitung.
  Die anschließenden Workflow-Änderungen bereiten den unsignierten Release-Prüflauf
  und einen separat angeforderten TestFlight-Upload vor.
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

## Abgenommenes Signatur-Update 0.5.1

1. Die Bundle-ID `de.smartplanhofmann.office` ist im Flutter-iOS-Projekt gesetzt.
   Sie wurde bereits für den installierten TestFlight-Build 108 verwendet.
2. Die Online-Konfiguration für Geräte- und Simulator-Builds ist in den Workflows
   gesetzt. Der unsignierte Release-Prüflauf kontrolliert API-URL/API-Version,
   die erzeugte Bundle-ID und Build-Nummer. Für `f335361` bestehen Codeanalyse,
   alle 34 App-Tests und die Windows-/iOS-Builds; siehe `deploy/hetzner/ABNAHME.md`.
3. Bestehende Apple-Zugänge und die GitHub-Secrets wiederverwenden. Der Nutzer
   hat keinen lokalen Mac. Der aktuelle Workflow archiviert unsigniert und
   signiert beim Export für TestFlight; kein neues Apple-Konto erforderlich.
4. Nutzer meldete mitscrollende Berichtsseite beim Zeichnen. Version 0.5.1 ergänzt
   `app/lib/signature_editor.dart`: Vorschaufeld antippen, im separaten Querformat-
   Editor unterschreiben, „Fertig“ übernimmt die Vorschau, Abbrechen verwirft Änderungen.
   Der endgültige Signieraufruf braucht weiterhin Name und Dokumentbestätigung.
   Nach der Übergabe für das TestFlight-Update bestätigte der Nutzer am
   23. Oktober: „die tests waren alle erfolgreich“. Der Signatur-Prüflauf gilt
   damit als vom Nutzer abgenommen; die genaue neue Buildnummer wurde nicht genannt.
5. Bereits bestätigt: Windows-Projekt erscheint auf dem iPhone; dort erstellter
   und unterschriebener Bericht ist als PDF mit Text/Unterschrift unter Windows
   sichtbar. Laut Nutzer sind die Rechteprüfungen bereits durchgeführt; die
   erneute Abfrage soll übersprungen werden. PDF-Teilen und weitere Last-/
   Betriebsabnahme bleiben gesonderte Punkte.

## Nächste Stufe: optionale Dokumentablage 0.6

Der Nutzer hat sich am 23. Oktober auf Hetzner als Standard festgelegt:
Projektmanagement, Benutzer, Datenbank und Original-PDFs bleiben zentral dort.
PDFs können zusätzlich in einer wählbaren Ablage gespeichert werden, etwa in
OneDrive-Projektordnern. Eine zusätzliche NAS-Ablage ist kein vollständiger
Vor-Ort-Betrieb. OneDrive ist eine Option, keine Voraussetzung für Smartplan.

Vorbereitet sind `backend/online/storage.py` mit ausdrücklicher Auswahl in der
App, privates Serververzeichnis, persönliches OneDrive und HTTPS-WebDAV für
geeignete Clouds/NAS. Weitere Adapter können ergänzt werden. S3, SFTP und direkte
SMB-Verbindungen sind nicht implementiert. Standard ohne Auswahl: keine zusätzliche
Ablage; Projektarbeit und PDFs bleiben trotzdem in Smartplan verfügbar.

Der Online-OneDrive-Adapter `backend/online/onedrive_connector.py` nutzt
Authorization Code + PKCE mit einmaligem, verschlüsseltem PostgreSQL-State und
einem Formular-Callback unter `/api/v1/storage/callback`. Microsoft-Tokens sind
verschlüsselt. Netzwerkaufrufe halten keinen globalen Datenbank-Lock und haben
ein begrenztes Gesamtbudget. Ein eigener Projektordner liegt im engen App-Ordner;
bereits vorhandene andere OneDrive-Projektordner werden nicht eingelesen.

Die vorhandene Serverinstallation benötigt `update-online.sh`; `git pull` allein
aktualisiert die installierte Codekopie nicht. `configure-storage.sh` fragt
Anschlussdaten verdeckt am Server ab und erhält vorhandene Daten, MFA-Schlüssel
und andere Anschlüsse. Sichere Aktualisierung, Registrierung und Abnahmeschritte:
`deploy/hetzner/online/STORAGE.md`. Die laufende Nutzer-VM ist noch nicht mit dieser
Stufe aktualisiert und ein echtes Microsoft-Konto ist noch nicht verbunden.

Nach erfolgreichen CI-Prüfungen erst den Online-Dienst aktualisieren, dann den
iPhone-Client über den bestehenden TestFlight-Weg verteilen. Bestehende Apple-
Zugänge wiederverwenden. Ein neues allgemeines Windows-Paket erst nach Klärung
der unten offenen Herausgebersignierung verteilen; der Windows-Prüfbuild ist
weiterhin unsigniert. Die bisherige Online-Windows-App kann den bestehenden
OneDrive-Upload-Endpunkt nutzen, wenn OneDrive serverseitig als Ziel ausgewählt
und verbunden ist.

Künftige Updates: erst Prüfungen abwarten, dann den Workflow „iPhone TestFlight“
manuell mit `upload_to_testflight` starten, nach Apples Verarbeitung der bestehenden
Gruppe „Smartplan intern“ zuordnen und auf dem iPhone aktualisieren. Die aktuelle
Abacus-GitHub-Integration kann laut Abacus-Bericht den Upload-Lauf nicht selbst
starten. TestFlight-Builds sind jeweils 90 Tage nutzbar; rechtzeitig einen neuen
Build bereitstellen. Die Node.js-20-Warnung der Actions ist eine spätere
Wartungsaufgabe und hat den erfolgreichen Lauf nicht blockiert.

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
- Native iPhone-App, Signatur-Update 0.5.1 und Rechteprüfungen sind vom Nutzer
  bestätigt; zusätzliche Last-/Betriebsprüfungen bleiben offen.
- Speicherstufe 0.6: technisch vorbereitet, noch nicht auf dem Nutzer-Server
  installiert. Echte Microsoft-Zustimmung/Dateiablage stehen noch aus.
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

Der anschließende iPhone-Prüflauf
[39852877486](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/39852877486)
ist für `0ee80c0` erfolgreich: alle 27 App-Tests samt echtem Backend und der
unsignierte Geräte-Release inklusive Online-Konfiguration und App-Kennung.
Auch die vollständigen Projektprüfungen
[39852877525](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/39852877525)
sind grün. Dies war der unsignierte Nachweis vom 22. Oktober; die am 23. Oktober
bestätigte TestFlight-Installation und der gemeinsame Geräteablauf sind in
`deploy/hetzner/ABNAHME.md` ergänzt. Dort stehen auch die anschließenden grünen
Prüfläufe und die Nutzerbestätigung für den separaten Signaturdialog 0.5.1.
