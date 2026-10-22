# Smartplan Office auf das iPhone (TestFlight) – ohne Mac

Gebaut und signiert wird ausschließlich auf GitHub Actions (`macos-latest`) mit dem Workflow
`.github/workflows/ios-testflight.yml`. Die Windows-App (lokal und Online-Pilot) bleibt unverändert.
Die iPhone-App verbindet sich nur mit `https://office.smartplan-hofmann.de` (API v1, HTTPS; keine ATS-Ausnahme nötig).

## Gewählter Signierweg und Begründung
`xcodebuild` mit Cloud-Signierung (`-allowProvisioningUpdates` + App-Store-Connect-API-Key).
Xcode erzeugt Distributionszertifikat und Provisioning-Profil selbst bei Apple – Sie müssen **keine**
Zertifikate, .p12-Dateien oder Profile manuell erzeugen und brauchen keinen Mac. Kein zusätzliches Werkzeug
(fastlane/Ruby) nötig, weniger bewegliche Teile. Upload mit `xcrun altool` und demselben Schlüssel.

**Wichtig – Rolle des API-Keys:** Cloud-verwaltete Distributionszertifikate darf laut Apple nur ein Schlüssel mit
Rolle **Admin** anlegen. Ein Key mit „App Manager“ reicht für Upload, aber nicht sicher für die Cloud-Signierung.
Erstellen Sie den Team-Key daher mit Rolle **Admin**. Schlüssel nur in GitHub Secrets speichern, nie im Code.

## Schritt für Schritt
1. **Apple Developer Program** beitreten (developer.apple.com/programs, kostenpflichtig ca. 99 €/Jahr). Ohne Mitgliedschaft kein TestFlight.
2. **Team-ID finden:** developer.apple.com/account → „Membership details“ → *Team ID* (10 Zeichen).
3. **Bundle-ID registrieren:** Certificates, Identifiers & Profiles → Identifiers → „+“ → App IDs → App →
   Beschreibung „Smartplan Office“, *Explicit* Bundle ID `de.smartplanhofmann.office`. Keine Zusatzfunktionen nötig.
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
7. **Workflow starten:** Actions → „iPhone TestFlight“ → „Run workflow“ → Branch wählen. Build-Nummer leer lassen
   (automatisch Laufnummer + 100, immer > 6) oder eine höhere Zahl als die letzte eingeben. Dauer ca. 15–30 Minuten.
   Fehlen Secrets, bricht der erste Schritt mit klarer Meldung ab. Die IPA liegt zusätzlich als Artefakt bereit.
8. **Exportkonformität:** In der App ist `ITSAppUsesNonExemptEncryption = false` gesetzt (nur Standard-HTTPS).
   Die Frage in App Store Connect entfällt dadurch normalerweise.
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
- **„Fehlende GitHub Secrets“** – Namen exakt wie oben, ohne Leerzeichen.
- **„No profiles / Cloud signing permission error“** – API-Key hat nicht die Rolle Admin, oder Bundle-ID nicht registriert.
- **„No suitable application records were found“** beim Upload – App in App Store Connect fehlt oder Bundle-ID abweichend.
- **„The bundle version must be higher…“** – Workflow mit höherer Build-Nummer erneut starten.
- **Ungültiger Schlüssel** – .p8-Inhalt vollständig inklusive BEGIN/END-Zeilen eintragen.
- **Max. Anzahl Distributionszertifikate** – unter Certificates alte, ungenutzte Distribution-Zertifikate widerrufen.
- **Build fehlt in TestFlight** – E-Mail von Apple prüfen (z. B. fehlende Datenschutz-Texte), Verarbeitung abwarten.

## Kosten-Hinweis
Bei privaten Repositories zählen macOS-Minuten mit Faktor 10 gegen das kostenlose GitHub-Kontingent
(Free: 2.000 Minuten/Monat ≈ 200 macOS-Minuten). Ein Lauf kostet ca. 15–30 macOS-Minuten. Öffentliche Repos: kostenlos.

## Technische Änderungen
- Bundle-ID `de.smartplanhofmann.office` (Tests `.RunnerTests`); DEVELOPMENT_TEAM nur im CI. Deployment Target iOS 15.0 (passt).
- Info.plist: `ITSAppUsesNonExemptEncryption=false`, `NSPhotoLibraryAddUsageDescription` (vorsorglich für Teilen/Sichern
  über `printing`). `file_selector` nutzt den Dokumentenauswähler und braucht keinen Text. Anzeigename „Smartplan Office“ unverändert.
- AppIcon geprüft: alle Größen vorhanden, 1024er Marketing-Icon RGB ohne Alpha – keine Änderung nötig.
- `checks.yml`: macOS-Simulator-Build mit Online-Defines; Windows-Jobs unverändert.
