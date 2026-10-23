# Nächste Stufe: gemeinsame Daten auf Windows und iPhone

Stand: 23. Oktober 2026. Privater Testserver und HTTPS eingerichtet;
Online-Pilot auf Hetzner aktiviert und unter Windows samt VM-Neustart bestätigt;
gemeinsamer Windows-/iPhone-Ablauf und Signatur-Update 0.5.1 vom Nutzer bestätigt.

**Aktuelle Entscheidung:** Nach der zunächst kostenfreien lokalen Entwicklung
hat der Nutzer einen Hetzner-CAX11-Testserver in Nürnberg eingerichtet. Die
ausgewählte Übersicht zeigte 7,69 Euro netto bzw. 9,15 Euro mit 19 Prozent
Umsatzsteuer monatlich einschließlich Hetzner-Backups und IPv4. Ein separates
Sicherungsziel und gegebenenfalls eine Domain sind darin nicht enthalten.
SSH, ARM-Backend-Tests und systemd-Testdienst sind bestätigt. Auch Windows-Zugriff
über SSH, fiktive Fachabläufe, manuelle Sicherung und Datenzugriff nach VM-Neustart
sind bestätigt. Der separate Online-Pilot ist inzwischen über HTTPS bereitgestellt;
Windows-Anmeldung, fiktiver Fachablauf und Wiederanlauf nach VM-Neustart sind vom
Nutzer bestätigt. Siehe
[HETZNER_START.md](HETZNER_START.md).
Die lokale Kundenverwaltung in Version 0.4.0
bleibt separat nutzbar; der gemeinsame iPhone-Zugriff erfolgt inzwischen über
die installierte TestFlight-App. Einzelbelege stehen in
[ABNAHME.md](deploy/hetzner/ABNAHME.md).

**Architekturentscheidung vom 23. Oktober:** Das gesamte Projektmanagement samt
Benutzern, Datenbank und Original-PDFs bleibt auf Hetzner. PDFs werden optional
zusätzlich in einer gewählten Dokumentablage gespeichert, beispielsweise je
Projekt in OneDrive. Die Speicheranschlüsse sind austauschbar; eine solche
zusätzliche Ablage verlagert nicht die Smartplan-Datenbank. Die neue Stufe 0.6
ist in Vorbereitung: [Speicheranschlüsse](deploy/hetzner/online/STORAGE.md).

## Ausgangslage und Ziel

Die Windows-App, Starter, Sicherung und Wiederherstellung sind auf dem Nutzer-PC
geprüft. Ein eigener Hetzner-Testserver ist jetzt vorhanden. Der Nutzer hat
Windows und ein iPhone; ein Mac ist nicht vorhanden. Der aktuelle iOS-Simulator-
Build läuft auf dem macOS-Rechner der GitHub-CI.

Die gemeinsame Testdatenbasis ist auf beiden Geräten bestätigt: Ein in Windows
angelegtes Projekt kann auf einem berechtigten iPhone geöffnet und ein dort
erstellter Bericht anschließend unter Windows gelesen werden. Für diesen
Geräteablauf werden fiktive Daten verwendet; die Übernahme des echten Windows-
Datenbestands erfolgt erst nach einem getrennt geprüften Migrationslauf.

## Empfohlener Betriebsweg

Geplant ist eine kleine Hetzner-Cloud-VM in Deutschland mit eigener HTTPS-Adresse,
PostgreSQL, dauerhaftem Speicher und getrennten Sicherungen. Hetzner Cloud ist
kein betreuter Anwendungsbetrieb: Zuständigkeit für Updates, Überwachung und
Wiederherstellung muss vor dem echten Einsatz feststehen. Ausgangspunkt für den
Test sind 2 vCPU, 4 GB RAM und 40 GB SSD (ARM64, Ubuntu 24.04 LTS).
Nutzerzahl, PDF-Datenmenge und Lasttests bestimmen die endgültige Größe.
Der Basistarif samt Hetzner-Backups und IPv4 wurde vor Bestellung geprüft;
weitere Leistungen werden vor einer zusätzlichen Buchung geprüft.

Das bestehende Microsoft-365-Family-Konto bleibt als Dokumentablage vorgesehen.
Die gemeinsame Datenbank wird durch das Backend verwaltet. Ein OneDrive-App-Ordner
stellt weder die gemeinsame Datenbank noch deren vollständige Sicherung bereit.

## Lieferpakete vor der ersten Bereitstellung

Der [Online-Pilot 0.5](deploy/hetzner/online/README.md) implementiert einen ersten
prüfbaren Teil: PostgreSQL-Schema, versionierte API mit Gunicorn, TOTP-/Recovery-
Anmeldung, separate Windows-Online-Konfiguration und lokale PostgreSQL-Sicherung
mit Wiederherstellung in eine neue Datenbank. Die bisherige SQLite-Anwendung
bleibt separat. Öffentliche Installation und 401-Test sind auf Hetzner bestätigt;
Windows-Online-Anmeldung und fiktiver Fachablauf mit Unterschrift/PDF ohne
SSH-Fenster sowie Datenzugriff nach VM-Neustart sind vom Nutzer bestätigt.
Die TestFlight-App ist inzwischen installiert; Projekt, Bericht, Signatur und
PDF sind auf Windows und iPhone bestätigt. Echte Datenübernahme, unabhängige
Sicherung und reale OneDrive-Verbindung bleiben offen.

| Paket | Konkretes Ergebnis | Nachweis |
| --- | --- | --- |
| Produktions-API und Datenhaltung | Versionierte API, PostgreSQL-Schema, Migrationen und Transaktionen; bestehende Rechte bleiben pro Abruf wirksam | Die bisherigen Rechte-/Signaturfälle bestehen auch gegen PostgreSQL; parallele Änderungen verlieren keine bestätigten Daten |
| Datenübernahme | Werkzeug für eine überprüfte Kopie der lokalen Sicherung, einschließlich Konten, Projekten, Zuordnungen, Berichten und PDF-Bytes | Anzahl und Beziehungen stimmen; signierte PDFs sind byteidentisch; alte Sitzungen werden nicht übernommen; Quelldaten bleiben erhalten |
| Anmeldung und Konfiguration | Festgelegte Anmeldung mit MFA für den gemeinsamen Betrieb; sichere Bereitstellung von Schlüsseln; getrennte Testkonfiguration | Berechtigter Zugriff auf zwei Geräten; Rechteentzug und Sperrung greifen; kein Standardkonto oder Schlüssel im Repository |
| Betriebspaket | Start-/Releaseanweisungen, HTTPS, persistente Daten, Gesundheitsprüfung, geschützte Protokolle und Wiederanlauf | Neustart erhält Daten; Gesundheitsprüfung belegt Datenbankzugriff; unangemeldete Fachabrufe bleiben gesperrt |
| Online-Sicherung | Automatische Datenbanksicherung und Wiederherstellung an einem getrennten Ziel | Wiederherstellung in einer neuen Testinstanz mit identischen unterschriebenen PDF-Dateien |
| OneDrive Personal | Registrierte Microsoft-App, passende Callback-Adresse, geschützter Tokenspeicher und tatsächlicher Upload | Ein freigegebener unterschriebener Bericht ist im eigenen App-Ordner vorhanden; erneute Anmeldung und Fehler sind geprüft |
| iPhone-Testpaket | Eigene Bundle-ID, Signierung und gewählter Testverteilungsweg; HTTPS-Adresse als App-Konfiguration | Installation und kompletter Projekt-/Berichts-/PDF-Ablauf auf dem echten iPhone |

Die gemeinsame Domänenlogik besitzt inzwischen einen PostgreSQL-Adapter mit
expliziten Migrationen und Transaktionen. Die öffentliche API läuft mit
Flask/Gunicorn hinter Caddy. Der Python-Standardbibliothekserver bleibt der
getrennte lokale Pilot; die alte SQLite-Datenbank wurde nicht übernommen.

Der davon getrennte private systemd-Pilot hat Dienststart, Windows-Fachablauf,
manuellen Sicherungslauf und VM-Wiederanlauf bestanden. Siehe die
[Abnahme](deploy/hetzner/ABNAHME.md). Die Gesundheitsantwort dieses Piloten
identifiziert den Prozess. Der separate Online-Pilot besitzt inzwischen eine
Bereitschaftsprüfung mit Datenbankzugriff, die vor Aktivierung erfolgreich
ausgeführt wurde. Die spätere iPhone-Abnahme ist inzwischen ebenfalls bestätigt.

## iPhone-Verteilung

Der Apple-Developer-Zugang und die Signierung über GitHub Actions sind eingerichtet.
Der Nutzer hat die native App über TestFlight auf dem echten iPhone installiert
und den gemeinsamen HTTPS-Datenstand bestätigt. Ein eigener Mac wird dafür nicht
benötigt. Der Workflow archiviert unsigniert und signiert beim IPA-Export.
Private Schlüssel bleiben in GitHub Secrets. Weitere Updates werden nach grünen
Prüfläufen über den manuell gestarteten TestFlight-Upload verteilt.

## Noch benötigte Angaben

1. Zahl der ersten Nutzer und Geräte sowie Zuständigkeit für den laufenden Betrieb.
2. Domain/DNS inzwischen geklärt: Wix-Zugriff vorhanden, A-Eintrag für
   `office.smartplan-hofmann.de` auf die VM am 22. Oktober bestätigt.
3. Apple-Developer-Zugang und TestFlight sind eingerichtet; keine neue Anmeldung nötig.
4. Zugang zur Microsoft-Appregistrierung für das bestehende Family-Konto.

Diese Angaben werden schrittweise geklärt. Konto und Basistarif sind geklärt;
ein weiterer Server muss nicht bestellt werden. DNS ist eingerichtet; das
[HTTPS-Einrichtungspaket](deploy/hetzner/https/README.md) läuft auf dem Nutzer-Server.
systemd-Start und Browseraufruf der statischen Seite über HTTPS ohne sichtbare
Zertifikatswarnung sind am 22. Oktober per Screenshot bestätigt. Der private Loopback-Pilot
mit SSH-Tunnel kann unabhängig davon geprüft werden; er erfüllt die öffentlichen
Lieferpakete nicht. Die laufende Betriebsverantwortung bleibt festzulegen.
Passwörter, Tokens, private Schlüssel und Zertifikate gehören nicht in den Chat.
Ohne konkrete Freigabe werden weder Hosting gebucht noch Apple-Mitgliedschaften
abgeschlossen oder Microsoft-Konten verbunden.

## Abnahme der nächsten Stufe

1. Windows meldet sich an der neuen Testadresse an und legt ein Projekt an.
2. Ein zugewiesener iPhone-Nutzer öffnet es; ein unberechtigter Nutzer erhält keinen Zugriff.
3. Der berechtigte Nutzer erstellt einen Bericht und zeichnet selbst eine Testunterschrift.
4. Windows öffnet das identische PDF; ein Entzug des Projektzugriffs sperrt weitere Abrufe.
5. Nach einem Neustart sind die Daten weiterhin vorhanden.
6. Eine getrennte Wiederherstellung und der reale OneDrive-Upload werden nachgewiesen.

Der gemeinsame Projekt-/Berichts-/PDF-Ablauf ist inzwischen bestätigt; laut Nutzer
wurden auch die Rechteprüfungen bereits durchgeführt und sollen nicht wiederholt
werden. Getrennte Wiederherstellung, echte OneDrive-Ablage und weitere Fachmodule
bleiben eigene Arbeitsschritte.

## iPhone über TestFlight
Schritt-für-Schritt-Anleitung ohne Mac: siehe [IPHONE_TESTFLIGHT.md](IPHONE_TESTFLIGHT.md) (Workflow `.github/workflows/ios-testflight.yml`).
