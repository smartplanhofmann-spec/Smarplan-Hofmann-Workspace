# Smartplan Office auf iPhone und iPad (TestFlight) – ohne Mac

Gebaut und signiert wird ausschließlich auf GitHub Actions (`macos-latest`) mit dem Workflow
`.github/workflows/ios-testflight.yml`. Der Flutter-Client wird gemeinsam mit Windows entwickelt.
Die iPhone-App verbindet sich nur mit `https://office.smartplan-hofmann.de` (API v1, HTTPS; keine ATS-Ausnahme nötig).

## Testupdate 0.7.0: Projektpläne und Offline-Speicherung

Für das nächste Update ist die App als `0.7.0+9` gekennzeichnet; der TestFlight-
Workflow ersetzt die Buildnummer weiter durch seine aufsteigende Laufnummer.
Die [Vorbereitung und Geräteabnahme](TESTUPDATE_0_7.md) beschreibt Reihenfolge,
Artefakte und Flugmodusprüfung. Der neue Client benötigt das freigegebene
Serverupdate mit Datenbankschema 2, bevor die Plan-/Offline-Anmeldung funktioniert.
Bestehende App-ID, Apple-Mitgliedschaft und Secrets werden weiterverwendet.

Ein separater `codex/testupdate-0.7-*`-Branch löst nur die unsignierte
Geräteprüfung aus. Der signierte Upload bleibt auf den manuellen Start des
bisherigen Releasebranchs beschränkt.

Die CI prüft jetzt im erzeugten Paket iPhone- **und** iPad-Unterstützung,
Face-ID-Beschreibung, Version, Buildnummer, API-Ziel und Bundle-ID. Beim
signierten IPA werden zusätzlich Codesignatur, erwartetes Team und tatsächliche
Keychain-Entitlements geprüft. Das geprüfte IPA samt Manifest und SHA-256-Datei
wird vor dem separat angeforderten TestFlight-Upload als Artefakt gesichert.
Die Quellprüfung und Paketprüfungen liefen hier erfolgreich; ein nativer
macOS-/Windows-Build dieses neuen Standes wurde hier noch nicht ausgeführt.

## Vorbereiteter Signierweg und aktueller Stand

Der Nutzer hat die Apple-Mitgliedschaft am 22. Oktober 2026 als Einzelunternehmer
für 99 Euro pro Jahr bestellt. Am 23. Oktober bestätigte er die installierte
TestFlight-App nach Abacus' Meldung zu Build 108 und den gemeinsamen
Windows-/iPhone-Berichtsablauf. Eine erneute Bestellung ist nicht nötig.

Vorbereitet ist `xcodebuild` mit automatischer Signierung
(`-allowProvisioningUpdates` + App-Store-Connect-API-Key) auf einem macOS-Runner.
Ein eigener Mac ist für diesen Ablauf nicht erforderlich. Ob Xcode auf einem
frischen Runner die erforderlichen Signieridentitäten und Profile erhält,
war beim ersten unsignierten Nachweis noch offen. Inzwischen wurde die
Archivierung auf unsigniert umgestellt; die Distributionssignierung erfolgt beim
Export. Der Nutzer bestätigte die anschließend per TestFlight installierte App.
Upload mit `xcrun altool` und demselben Schlüssel.

### Update 0.5.1: Unterschrift im Querformat

Im Bericht das Unterschriftenfeld antippen. Die separate Zeichenfläche öffnet
im Querformat und erfasst den Stift/Finger ab dem ersten Kontakt, ohne die
Berichtsseite zu scrollen. „Neu zeichnen“ leert die aktuelle Bearbeitung,
„Abbrechen“ verwirft sie und „Fertig“ übernimmt die Unterschrift in die Vorschau.
Der Name und die Dokumentbestätigung werden beim endgültigen Speichern geprüft.
Die Zeichenfläche behält das Seitenverhältnis des PDF-Felds bei.

Die Codeanalyse und alle 34 App-Tests sowie die Windows-, Simulator- und
unsignierten Geräte-Builds für `f335361` sind erfolgreich. Nach der Übergabe
für das TestFlight-Update bestätigte der Nutzer am 23. Oktober:
„die tests waren alle erfolgreich“. Die Geräteabnahme des Signatur-Updates ist
in [ABNAHME.md](deploy/hetzner/ABNAHME.md) festgehalten.

Für weitere Updates den bestehenden Workflow nach erfolgreichen Prüfungen
manuell mit `upload_to_testflight` starten. Die automatische Buildnummerierung
steigt mit jedem Lauf weiter; eine manuell gewählte Nummer muss über der letzten
hochgeladenen liegen. Nach Apples Verarbeitung den Build der bestehenden Gruppe
„Smartplan intern“ zuordnen, falls dies nicht automatisch erfolgt, und über
TestFlight aktualisieren. Anschließend erste Striche, Querformat, Abbrechen und
Rückkehr zur Berichtsansicht am echten iPhone prüfen, auch mit Rotationssperre.

TestFlight-Builds sind jeweils 90 Tage nutzbar. Für die weitere Testverteilung
rechtzeitig einen neuen Build bereitstellen, auch wenn der Code unverändert ist.
Die aktuelle Abacus-GitHub-Integration kann den Workflow laut Abacus-Bericht
nicht selbst starten; der Nutzer startet den Upload über „Run workflow“.
Die im erfolgreichen Lauf gemeldete Warnung „Node.js 20 is deprecated“ blockiert
das Update nicht. Verwendete GitHub Actions bei einer späteren Wartung aktualisieren.

### Technischer Nachweis vom 22. Oktober 2026

Commit `0ee80c0` ist auf GitHub geprüft:

- [iPhone-Prüflauf 39852877486](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/39852877486)
  erfolgreich: App-Analyse, alle 27 App-Tests einschließlich echtem Python-Backend,
  unsignierter iOS-Geräte-Release und Prüfung von API-URL/API-Version, Bundle-ID
  und Buildnummer. Artefakt `Smartplan-Office-iOS-UNSIGNED-105` ist kein installierbares IPA.
- [Projektprüfungen 39852877525](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/39852877525)
  vollständig erfolgreich, einschließlich Windows und iOS-Simulator.
- Der lokale Testserver verwendet seine numerische Loopback-Adresse, damit der
  Teststart auf macOS nicht an einer Reverse-DNS-Abfrage hängt. Anmeldung,
  Unterschrift und PDF werden weiterhin vollständig geprüft.
- Der Signier-/Upload-Job wurde bei diesem automatischen Lauf wie vorgesehen übersprungen.
  Apple-Signierung, TestFlight-Upload und Geräteinstallation wurden damit noch nicht geprüft;
  die spätere Bestätigung für Build 108 steht im aktuellen Stand oben.

**Wichtig – Rolle des API-Keys:** Cloud-verwaltete Distributionszertifikate darf laut Apple nur ein Schlüssel mit
Rolle **Admin** anlegen. Ein Key mit „App Manager“ reicht für Upload, aber nicht sicher für die Cloud-Signierung.
Erstellen Sie den Team-Key daher mit Rolle **Admin**. Schlüssel nur in GitHub Secrets speichern, nie im Code.

## Schritt für Schritt

Für das Update werden das bestehende Apple-Konto, die App-ID, der App-Store-Connect-
Eintrag und die vier bereits eingerichteten GitHub-Secrets wiederverwendet.
Die Schritte 2–6 dokumentieren die Ersteinrichtung; sie sind nicht erneut auszuführen.

1. **Apple Developer Program:** Mitgliedschaft und erster TestFlight-Zugang wurden
   inzwischen für Build 108 verwendet; für dieses Update ist keine neue Anmeldung nötig.
2. **Team-ID finden:** developer.apple.com/account → „Membership details“ → *Team ID* (10 Zeichen).
3. **Bundle-ID registrieren:** Certificates, Identifiers & Profiles → Identifiers → „+“ → App IDs → App →
   Beschreibung „Smartplan Office“, *Explicit* Bundle ID `de.smartplanhofmann.office`. Die Offline-Stufe verwendet die im Repository vorbereiteten Keychain-Entitlements; keine neue App-ID anlegen.
4. **App in App Store Connect anlegen:** appstoreconnect.apple.com → Apps → „+“ → Neue App: Plattform iOS,
   Name „Smartplan Office“ (falls belegt z. B. „Smartplan Office Hofmann“), Sprache Deutsch,
   Bundle-ID `de.smartplanhofmann.office`, SKU z. B. `smartplan-office-001`, Zugriff: Vollständig.
5. **API-Key erstellen:** App Store Connect → Benutzer und Zugriff → Integrationen → App Store Connect API →
   Team-Schlüssel → „+“ → Name „GitHub Actions“, Zugriff **Admin**. Notieren: *Key ID* und *Issuer ID* (oben).
   `.p8` herunterladen – geht nur **einmal**. Sicher aufbewahren.
6. **GitHub Secrets setzen:** Repository → Settings → Secrets and variables → Actions → „New repository secret“:
   - `APP_STORE_CONNECT_KEY_ID` – Key ID
   - `APP_STORE_CONNECT_ISSUER_ID` – Issuer ID
   - `APP_STORE_CONNECT_PRIVATE_KEY` – kompletter Inhalt der .p8 (mit Editor öffnen, inkl. `-----BEGIN PRIVATE KEY-----`/`-----END…`)
   - `APPLE_TEAM_ID` – Team-ID
7. **Workflow starten:** Actions → „iPhone TestFlight“ → „Run workflow“ → Branch
   `codex/smartplan-office-0.2` wählen. Dieser Branch ist zugleich der Standardbranch;
   der manuelle Start ist verfügbar, sobald die Workflow-Datei dort liegt.
   Build-Nummer leer lassen (automatisch Laufnummer + 100, mindestens Quell-Buildnummer) oder eine
   höhere Zahl als die letzte hochgeladene eingeben; mindestens die Quell-Buildnummer aus `pubspec.yaml`.
   Änderungen lösen zunächst einen unsignierten Prüflauf aus. Dieser führt Analyse,
   App-Tests einschließlich echtem lokalem Python-Backend und einen Online-Release-Build
   aus. Apple-Schlüssel werden diesem Job nicht bereitgestellt.
   Erst nach Apples Freischaltung und Einrichtung der vier Secrets bei einem
   **manuellen** Start `upload_to_testflight` aktivieren. Nur dann läuft der separate
   Signier-/Upload-Job; fehlende Secrets führen dort zu einer klaren Fehlermeldung.
   Das signierte IPA wird nach erfolgreichem Export als Artefakt bereitgestellt.
   Ein unsignierter Prüflauf erzeugt noch keine installierbare iPhone-App.
8. **Exportkonformität:** Der bestehende Flag `ITSAppUsesNonExemptEncryption = false` bleibt erhalten.
   Die App verwendet jetzt zusätzlich AES-GCM für lokale Dateien über `package:cryptography`;
   die frühere Beschreibung „nur Standard-HTTPS“ gilt nicht mehr. Der Flag allein belegt
   keine Ausnahme. Die Angaben im vorhandenen App-Store-Connect-Eintrag müssen vor
   einem echten Upload zur aktuellen Verschlüsselungsverwendung passen; eine rechtliche
   Einstufung wird nicht aus einer erfolgreichen technischen Buildprüfung abgeleitet.
9. **Interne Tester:** App Store Connect → App → TestFlight. Nach 5–30 Min. „Verarbeitung“ erscheint der Build.
   „Interne Tests“ → Gruppe anlegen → Tester (müssen Benutzer im App-Store-Connect-Team sein) hinzufügen → Build zuweisen.
10. **iPhone:** App „TestFlight“ aus dem App Store installieren, Einladungs-E-Mail öffnen → „Annehmen“ → „Installieren“.
11. **Erstanmeldung:** Online-Testkonto, Passwort, dann Authenticator-Code (MFA/TOTP). Wiederherstellungscodes sicher aufbewahren.

## Abnahmetest (nur fiktive Daten)
1. Windows-Online-Pilot: Testprojekt „Musterbau Test GmbH“ anlegen und dem iPhone-Benutzer zuweisen.
2. iPhone: Projekt öffnen, Bericht erfassen, unterschreiben, speichern, PDF ansehen.
3. Windows: dasselbe Projekt öffnen → identisches PDF mit Unterschrift prüfen.
4. Windows: Projektzuweisung entziehen → iPhone aktualisieren → Projekt darf nicht mehr sichtbar/abrufbar sein.
5. Lokale Windows-App starten: bisherige Daten, Unterschriften und PDFs unverändert vorhanden.

## Fehlerbehebung
- **„Fehlende GitHub Secrets“** – beim ausdrücklich angeforderten Upload die vier
  Namen exakt wie oben anlegen. Der unsignierte Prüflauf benötigt diese Secrets nicht.
- **„No profiles / Cloud signing permission error“** – API-Key hat nicht die Rolle Admin, oder Bundle-ID nicht registriert.
- **„No suitable application records were found“** beim Upload – App in App Store Connect fehlt oder Bundle-ID abweichend.
- **„The bundle version must be higher…“** – Workflow mit höherer Build-Nummer erneut starten.
- **Ungültiger Schlüssel** – .p8-Inhalt vollständig inklusive BEGIN/END-Zeilen eintragen.
- **Max. Anzahl Distributionszertifikate** – unter Certificates alte, ungenutzte Distribution-Zertifikate widerrufen.
- **Build fehlt in TestFlight** – E-Mail von Apple prüfen (z. B. fehlende Datenschutz-Texte), Verarbeitung abwarten.

## Kosten-Hinweis
Dieses Repository ist öffentlich. Standardmäßige von GitHub gehostete Runner
sind dafür kostenfrei. Bei einem späteren Wechsel auf ein privates Repository
gelten das Kontingent und die aktuellen Runner-Preise des GitHub-Kontos.

## Technische Änderungen
- Bundle-ID `de.smartplanhofmann.office` (Tests `.RunnerTests`); DEVELOPMENT_TEAM nur im CI. Deployment Target iOS 15.0 (passt).
- Info.plist: `ITSAppUsesNonExemptEncryption=false`, `NSPhotoLibraryAddUsageDescription` (vorsorglich für Teilen/Sichern
  über `printing`). `file_selector` nutzt den Dokumentenauswähler und braucht keinen Text. Anzeigename „Smartplan Office“ unverändert.
- AppIcon geprüft: alle Größen vorhanden, 1024er Marketing-Icon RGB ohne Alpha – keine Änderung nötig.
- `checks.yml`: macOS-Simulator-Build mit Online-Defines; Windows-Jobs unverändert.
