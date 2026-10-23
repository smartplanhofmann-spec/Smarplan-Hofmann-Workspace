# Abnahme des privaten Hetzner-Piloten

Abnahmestand: 23. Oktober 2026. Bestätigungen aus dem Nutzergespräch und die
technischen Prüfungen werden getrennt aufgeführt. Dieser Stand betrifft den
privaten Pilotzugriff, den anschließenden Online-Piloten und die unten ausdrücklich
bestätigten Windows-/iPhone-Schritte mit fiktiven Testdaten.

## Auf dem Nutzer-Testserver und Windows bestätigt

| Prüfung | Ergebnis und Nachweis |
| --- | --- |
| Grundinstallation | CAX11 ARM64 in Nürnberg, Ubuntu 24.04, nach Aktualisierung Kernel `6.8.0-147-generic`; SSH-Anmeldung mit eigenem Schlüssel |
| ARM-Abhängigkeiten | Pinned Python-Pakete mit ARM64-Wheels installiert, Erfolgsausgabe im Screenshot |
| Backend-Tests auf ARM | 32 Fälle ausgeführt: 31 bestanden, ein ausschließlich für Windows bestimmter Fall übersprungen |
| systemd-Installation | Privater Dienst und Backup-Timer gestartet; Dienststart und nächster Timertermin im Screenshot |
| Pilotkonto | Getrenntes Geschäftsführungskonto über die verdeckte Passwortabfrage angelegt, danach Dienst wieder gestartet; vom Nutzer bestätigt |
| Windows-Verbindung | PowerShell-Abfrage über den lokalen SSH-Tunnel lieferte `status=ok` und `launch_id=smartplan-private-pilot` |
| App-Funktionstest | Nutzer bestätigte fiktiven Kunden, Projekt „Server-Test“, Servicebericht, Unterschrift und PDF-Ausgabe in der Windows-App |
| Datenbanksicherung | Manueller Start von `smartplan-pilot-backup.service`: `code=exited, status=0/SUCCESS`, Meldung „Sicherung erstellt“ im Screenshot |
| Wiederanlauf nach VM-Neustart | Nach erneutem SSH-Verbindungsaufbau und Start der App bestätigte der Nutzer, dass Testdaten und unterschriebenes PDF weiterhin vorhanden sind |

Die manuelle Bestätigung nach dem VM-Neustart belegt das erneute Öffnen der
Testdaten. Es wurde dabei kein manueller Bytevergleich des PDFs behauptet.
Der Timer war bei Installation aktiv; der manuell ausgelöste Sicherungslauf
bestätigt den Sicherungsdienst. Ein späterer kalendergesteuerter Lauf wurde
nicht zusätzlich per Screenshot abgenommen.

Das private Datenverzeichnis ist `/var/lib/smartplan-pilot`, lokale Sicherungen
liegen darunter in `backups`. Die zuvor lokal auf Windows verwendete Datenbank
wurde weder kopiert noch ersetzt. Die Tests betreffen einen getrennten
Pilotdatenbestand. Das Passwort und der private SSH-Schlüssel bleiben beim Nutzer.

## Automatisierte Prüfungen der Dienstdateien

Für Code-Stand `20592f6dddb6089c6df01655276dc33ffb34dc1f` bestanden in der
Entwicklungsumgebung drei zusätzliche Linux-Prüffälle mit dem echten
nicht privilegierten Startprozess:

- Nur Loopback lauscht; unangemeldete Fachabrufe erhalten 401. Ein synthetischer
  Kunde, Projekt und unterschriebener Bericht können erzeugt werden. Nach einem
  Prozessneustart sind Verknüpfung und PDF-Bytes identisch.
- Zwei Sicherungen einer laufenden Testinstanz haben Modus 0600, passende
  SHA-256-Prüfsummen, gültige Beziehungen und identische PDF-Bytes. Die
  Wiederherstellung in eine neue Testdatei verwirft Sitzungen.
- Fehlende Datenkonfiguration und ungültiger Port starten keine Datenbank;
  eine Sicherung vor der ersten Datenanlage erzeugt keine leere Datei.

Der erste und zweite Punkt werden in einem gemeinsamen Ende-zu-Ende-Test
geprüft. Dazu kommen zwei separate Fehler-/Leerzustandsfälle: insgesamt drei.
Bash-Syntax, Zurückweisen der Installation ohne root, relative Dokumentlinks
und die systemd-Unit-Syntax wurden ebenfalls geprüft. systemd selbst läuft
in der Entwicklungsumgebung nicht als PID 1; der reale Dienststart wurde
deshalb anhand der oben aufgeführten Hetzner-Ausgabe abgenommen.

Im [GitHub-Lauf 39495574820](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/39495574820)
haben Backend- und Flutter-Jobs erfolgreich abgeschlossen; der Flutter-Job
enthält auch die drei Linux-Dienstprüfungen. Ein Windows-Paket wurde erzeugt.
Der Gesamtlauf ist fehlgeschlagen, weil GitHub nach mehreren Versuchen keinen
gehosteten macOS-Runner zuweisen konnte und einen internen Fehler meldete.
Daraus wird kein erfolgreicher iOS-Simulator-Build für diesen Lauf abgeleitet.

## DNS und installierte HTTPS-Einrichtungsseite

Wix-Verwaltungszugriff ist bestätigt. Der Nutzer ergänzte den A-Eintrag
`office.smartplan-hofmann.de` → `116.203.43.69`; die Windows-Abfrage
`Resolve-DnsName` bestätigt ihn am 22. Oktober. Die bisherigen drei A-Einträge
der Wix-Hauptseite sind im gespeicherten DNS-Screenshot weiterhin vorhanden.

Das [HTTPS-Paket](https/README.md) wurde mit dem echten Caddy 2.11.7 ohne root
lokal geprüft: verifiziertes TLS mit eigener Test-CA, Ablehnung ohne Vertrauen,
HTTP-Weiterleitung, statische Seite und gesperrte API-/Gesundheitsendpunkte.
Bash- und systemd-Syntax sind geprüft. Kein öffentlicher API-Proxy ist enthalten.

Nach der Korrektur `f1e8f9c` der DNS-Vorprüfung ist die Installation auf Hetzner
bestätigt: Der Screenshot zeigt `smartplan-https.service` als aktiviert und
`active (running)`, Prozess `caddy`. Der Nutzer hatte zuvor die zusätzlichen
Firewall-Regeln für TCP 80/443 bestätigt. Ein weiterer Screenshot vom
22. Oktober zeigt `https://office.smartplan-hofmann.de/` mit der korrekten
Einrichtungsseite ohne sichtbare Zertifikatswarnung. Dies bestätigt den
öffentlichen HTTPS-Seitenabruf. Zertifikatserneuerung und HTTP-Weiterleitung
wurden auf dem Nutzer-Server nicht gesondert abgenommen. Die 503-Sperre der
App-Endpunkte ist lokal getestet, noch nicht separat am öffentlichen Host.

## Online-Pilot auf Hetzner und CI-Build bestätigt

Der separate [Online-Pilot 0.5](online/README.md) ist inzwischen im Code vorbereitet.
In der Entwicklungsumgebung bestehen 19 PostgreSQL-/Anmeldefälle einschließlich
Dump/Restore, Rechteentzug und paralleler Unterschrift. Ein weiterer echter
Caddy/Gunicorn/PostgreSQL-Test prüft MFA, PDF und API-Neustart über verifiziertes
TLS. Flutter-Analyse und alle 27 App-Tests bestehen; die bisherigen 32 lokalen
Backend-Fälle laufen weiterhin mit einem erwarteten Windows-Skip auf Linux.

Der Nutzer hat den Online-Piloten inzwischen auf derselben VM installiert.
Sein Screenshot zeigt Gunicorn 26.2.0 mit zwei Workern auf `127.0.0.1:8766`.
Ein getrenntes Online-Geschäftsführungskonto wurde über die verdeckte
Passwortabfrage angelegt. Der Aktivierungs-Screenshot vom 22. Oktober um
18:59 UTC zeigt gültige Caddy-Konfiguration und die erfolgreiche öffentliche
Prüfung: „Versionierte Online-API über HTTPS erreichbar; unangemeldeter
Projektzugriff gesperrt (401)“. Der Aktivierungsablauf führt vor der Umschaltung
auch die lokale PostgreSQL-Sicherung aus und bricht bei deren Fehler ab.
Es wurden keine echten lokalen Windows-Daten übernommen.

Der [GitHub-Lauf 39835146915](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/39835146915)
für `6777fb9ee64eaf05d08cfc13be98049641b663bc` hat insgesamt erfolgreich
abgeschlossen: Online-API, HTTPS, Backend, Flutter sowie beide nativen Builds
(Windows und iOS-Simulator). Das separate Online-Artefakt heißt
`Smartplan-Office-Windows-Online-Pilot`, Größe 15,4 MB, SHA-256
`9915d6c401ac830cbae3970ce5881fe94115c23662ca66ce88bdedc180538a1c`.
Der iOS-Simulator-Build ist weiterhin keine signierte Geräteinstallation.

### Windows-Online-Abnahme durch den Nutzer

Der Nutzer bestätigte anschließend die Anmeldung in der separaten Online-App.
Die App fordert dafür die Authenticator-Bestätigung an; eine Einzelprüfung
seiner privat aufzubewahrenden Wiederherstellungscodes wurde nicht verlangt.
Das SSH-Fenster war laut Nutzer schon geschlossen, bevor er die App startete:
Der Ablauf benötigt keinen geöffneten SSH-Tunnel.

Auf die Anleitung, einen fiktiven Kunden und das Projekt „Online-Test“ anzulegen,
einen Servicebericht mit Testnamen zu unterzeichnen und das PDF zu öffnen,
bestätigte der Nutzer die erfolgreiche Durchführung. Anschließend wurde ein
geordneter VM-Neustart per SSH `reboot` angeleitet. Nach Wartezeit, erneuter
App-Anmeldung und Prüfung von Projekt und unterschriebenem PDF bestätigte er:
„ja passt alles“. Damit sind der Online-Windows-Fachablauf und der Wiederanlauf
nach VM-Neustart manuell bestätigt. Ein manueller Bytevergleich des PDFs wurde
dabei nicht behauptet; dieser ist separat durch die automatisierten Tests belegt.

Windows zeigte beim ersten Start SmartScreen für das unsignierte Paket. Der
Nutzer führte es manuell aus und verlangte die Bearbeitung im nächsten Update.
Vertrauenswürdige Signierung/Installer samt Prüfung des tatsächlichen Downloads
sind dafür im Umsetzungsplan vorgezogen; die Warnung ist noch nicht behoben.

## Geräteabnahme und offener Betrieb

### Gemeinsamer Geräteablauf am 23. Oktober bestätigt

Abacus meldete TestFlight-Build 108 in der internen Gruppe „Smartplan intern“.
Der Nutzer bestätigte anschließend die Installation/Anmeldung auf dem iPhone,
das Öffnen des unter Windows angelegten Projekts „iPhone-Test“ und folgenden
Fachablauf: auf dem iPhone einen Servicebericht mit Testtext und Testunterschrift
abschließen, danach Text und Unterschrift im PDF unter Windows öffnen.
Auf die Frage nach vollständigem Text und Unterschrift antwortete er:
„ja das funktioniert“. Dies bestätigt den gemeinsamen Online-Datenstand und
die sichtbare PDF-Ausgabe. Ein manueller Bytevergleich oder ein eigener
Techniker-/Mehrbenutzertest wurde dabei nicht behauptet.

Dabei meldete der Nutzer einen Bedienfehler: Beim Zeichnen im eingebetteten
Unterschriftenfeld scrollt die Berichtsseite mit und der Strich beginnt verspätet.
Version 0.5.1 bereitet dafür einen separaten Vollbildeditor im Querformat vor:
Feld antippen, zeichnen, mit „Fertig“ in die Vorschau übernehmen. Abbrechen
verwirft nur die Bearbeitung; das abschließende Speichern mit Name und
Dokumentbestätigung bleibt erforderlich. Dieser neue Gesten-/Drehablauf muss
nach dem nächsten TestFlight-Update noch auf dem echten iPhone bestätigt werden.

### Weiterhin offen

- Mehrbenutzer-Rechteentzug am Nutzer-System und der neue Signaturdialog auf
  dem echten iPhone. Öffentlicher Projektzugriff ohne Anmeldung ist mit
  401 bestätigt. TCP 8765, 8766 und 5432 bleiben gesperrt.
- SmartScreen-Rückmeldung beim nächsten Windows-Update bearbeiten: gültige
  Herausgebersignierung und signiertes Installationspaket vorbereiten und prüfen.
- HTTPS-Erneuerung und Betrieb überwachen; Last-/Mehrbenutzerabnahme und
  geprüfte Datenübernahme gemäß [Betriebsplan](../../BETRIEB_UND_IPHONE.md).
- Wiederherstellung aus einer tatsächlichen Pilot-Serversicherung in eine
  getrennte Instanz; getrenntes verschlüsseltes Sicherungsziel, Aufbewahrung,
  Betriebsüberwachung und zuständige Betreuung. Die derzeitigen lokalen Kopien
  und Hetzner-Backups ersetzen dieses Lieferpaket nicht.
- Übernahme einer geprüften Kopie des echten Windows-Datenbestands und tatsächliche
  OneDrive-Verbindung. Die bestätigten Geräte-Schritte ersetzen diese Prüfungen nicht.

Die bestehende private Verbindung kann weiter für fiktive Tests verwendet werden.
`backend/server.py` wird nicht durch eine neue Firewallregel oder einen
öffentlichen Reverse-Proxy zur Produktions-API erklärt.
