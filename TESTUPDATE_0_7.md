# Testupdate 0.7.0 – Projektpläne auf Windows, iPhone und iPad

Dieser Stand bereitet das Testupdate vor. Die App ist mit Version `0.7.0+9`
gekennzeichnet. Es wurde noch kein neuer nativer Build ausgeführt, kein IPA
hochgeladen und kein Nutzer-Server aktualisiert.

## Reihenfolge

1. Den neuen Quellstand lokal prüfen:
   `python scripts/native-release.py source` sowie
   `python -m unittest discover -s scripts -p test_native_release.py -v`.
   Für native Prüfungen wird ein separater Branch mit dem engen Muster
   `codex/testupdate-0.7-*` verwendet. Ein Push dorthin ändert weder den
   laufenden Hetzner-Dienst noch den bisherigen Releasebranch.
2. GitHub **Development checks** für diesen Testbranch erfolgreich abschließen.
   Das umfasst App-/Backend-Tests, Windows-Release und iOS-Simulator. Der
   **iPhone TestFlight**-Workflow führt auf diesem Branch nur die unsignierte
   Geräte-Releaseprüfung aus. Der signierte Upload bleibt ausschließlich bei
   einem manuellen Start auf `codex/smartplan-office-0.2` möglich; ein Testbranch
   kann ihn auch durch die Upload-Checkbox nicht aktivieren.
3. Erst nach erfolgreichen Prüfläufen den in der Serveranleitung beschriebenen
   Sicherungs-/Migrations-/Updateablauf durchführen und den Online-Dienst mit
   Schema 2 nachweisen. Die bisherige Datenbank und die Geheimnisse nicht durch
   Beispieldaten ersetzen. Die Prüfung auf dem Testbranch führt das Serverupdate
   nicht selbst aus.
4. Den freigegebenen, geprüften Quellstand in den bestehenden Releasebranch
   übernehmen. Nach erfolgreichem Serverupdate den vorhandenen TestFlight-
   Workflow auf `codex/smartplan-office-0.2` manuell mit `upload_to_testflight`
   starten. Die bestehende Apple-Konfiguration wiederverwenden. Die Buildnummer
   muss über der letzten hochgeladenen Nummer liegen und mindestens der
   Quell-Buildnummer entsprechen.
5. Das Windows-Online-Testpaket in einen neuen Ordner entpacken; iPhone/iPad über
   die vorhandene TestFlight-Gruppe aktualisieren. Lokale Daten und vorhandene
   App-Daten nicht löschen. Erst dann die folgende Geräteabnahme durchführen.

Ein erfolgreicher Cloud-Test ersetzt weder einen nativen Build noch die
TestFlight-Verarbeitung oder die Geräteabnahme. Diese Schritte werden jeweils
mit ihren tatsächlichen Lauf-/Artefaktinformationen dokumentiert.

## Welche Pakete wofür gedacht sind

| Artefakt | Verwendung |
| --- | --- |
| `Smartplan-Office-Windows-Online-Pilot` | Für den gemeinsamen Server, ohne lokalen Python-Starter. |
| `Smartplan-Office-Windows` | Getrennte lokale Windows-Stufe, mit eigenem Python-Backend und Starter. |
| `Smartplan-Office-iOS-UNSIGNED-<Nummer>` | Geräte-Buildprüfung für iPhone/iPad; nicht installierbar. |
| `Smartplan-Office-iOS-<Nummer>` | Geprüftes signiertes IPA, Manifest und SHA-256; TestFlight-Upload ist weiterhin ausdrücklich gewählt. |

Jedes Windows-Paket enthält `RELEASE_MANIFEST.json` mit Version, vollständigem
Quell-Commit, API-Ziel, Schema-Voraussetzung, Offline-Umfang und SHA-256 der
enthaltenen Dateien. Die iOS-Artefakte enthalten das entsprechende Buildmanifest;
beim signierten IPA kommt `SHA256SUMS.txt` hinzu. Alle Pakete derselben Abnahme
müssen denselben Quell-Commit nennen.

Die lokale Windows-Stufe enthält jetzt auch `plans.py` und `plan_access.py`.
Ohne diese Dateien würde ihr kopierter Python-Server beim Import scheitern.
Die Paketprüfung kontrolliert sämtliche lokalen Python-Importe und die beiden
neuen nativen DLLs für sicheren Speicher und Geräteauthentifizierung.

## Werkzeuge auf den Build-Runnern

- Gepinntes Flutter 3.47.7 mit `flutter pub get --enforce-lockfile`.
- Windows x64: Visual Studio C++-Werkzeuge und ATL. Die CI prüft die Komponenten
  vor dem Build und nimmt die benötigten Laufzeit-DLLs mit ins Paket. Die
  optionale JNI/JVM-Suche eines transitiven Android-Pakets ist für diesen
  Windows-Client ausdrücklich deaktiviert; seine Windows-Funktionen verwenden
  Win32 und benötigen keine Java-Laufzeit.
- iOS: macOS/Xcode mit Swift-Tools mindestens 5.9, bestehende App-ID
  `de.smartplanhofmann.office`. iOS 15, iPhone und iPad bleiben aktiviert.
- Die neue Face-ID-Beschreibung und Keychain-Entitlements sind für
  Debug/Profile/Release eingebunden. Die signierten Entitlements werden am
  tatsächlichen IPA geprüft; eine statische Quellprüfung belegt noch keine
  funktionierende Schlüsselablage auf einem Gerät.

Das Windows-Paket ist weiterhin ein Testpaket ohne Authenticode-Installer.
Die bereits offene Herausgebersignierung/SmartScreen-Aufgabe wird dadurch nicht
als erledigt dargestellt. Sicherheitsfunktionen nicht zum Starten abschalten.

## Geräteabnahme mit fiktiven Daten

1. Online anmelden und auf iPhone/iPad ein freigegebenes Testprojekt und dessen
   Planliste öffnen. Einen Grundriss anlegen und zwei Wände zeichnen. Abwarten,
   bis die lokale Speicherung bestätigt ist und die Übertragung abgeschlossen ist.
2. Flugmodus aktivieren. Titel und Wandzeichnung ändern. Die App muss lokale
   Speicherung und ausstehende Übertragung unterscheiden.
3. App normal beenden und erneut öffnen. **Offline-Pläne entsperren** über
   Face ID/Touch ID/Geräteanmeldung öffnen. Titel und Zeichnung müssen erhalten
   sein. Auch Abbruch der Entsperrung prüfen: keine Offline-Daten öffnen.
4. Verbindung wieder einschalten und die App geöffnet lassen beziehungsweise
   erneut öffnen. Die Warteschlange muss fortsetzen. Danach auf Windows den
   identischen Planstand öffnen; keine doppelten Pläne oder Stände erzeugen.
5. Paralleländerung prüfen: denselben Plan auf Windows ändern, während das
   iPad offline daran arbeitet. Beim Abgleich müssen beide Fassungen erhalten
   bleiben. **Lokale Kopie behalten** darf den Serverstand nicht überschreiben.
6. Auf dem tatsächlichen iPad Hoch-/Querformat prüfen, auf dem iPhone kleine
   Zeichenfläche, Face ID, Gerätecode-Fallback und Wechsel in den Hintergrund.
7. Abmeldung bei ausstehenden Änderungen muss warnen und die Eingaben für
   erneute Online-Anmeldung erhalten. Ein anderes Konto darf diese Daten nicht
   sehen. Den Ablauf der siebentägigen Freigabe zusätzlich nach dem vereinbarten
   Testverfahren prüfen; die Uhrzeit des normalen Nutzergeräts dafür nicht
   ungeplant verändern.
8. Vorhandene Online-Berichte, Signaturen und PDFs nach dem Update erneut
   öffnen. Berichte und Medien brauchen in dieser Stufe weiterhin Verbindung.

Ergebnis je Gerät festhalten: Modell, Betriebssystem, Appversion/Buildnummer,
Quell-Commit des Manifests, Datum und Abweichungen. Keine Passwörter, Tokens oder
realen Kunden-/Projektdaten in Screenshots oder öffentliche Fehlerberichte geben.
