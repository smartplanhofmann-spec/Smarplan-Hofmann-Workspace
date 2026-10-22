# Smartplan-Testserver bei Hetzner

Stand: 22. Oktober 2026. Konto und CAX11-Testserver `smartplan-test` sind eingerichtet.
Ubuntu 24.04 wurde aktualisiert und mit Kernel `6.8.0-147-generic` neu gestartet.
SSH-Zugang von Windows, Firewall und Hetzner-Backups sind bestätigt. Auf dem
ARM64-Server wurden die Backend-Pakete installiert und 32 Testfälle ausgeführt:
31 bestanden, ein Windows-Fall erwartungsgemäß übersprungen. Ein echter Windows-
Datenbestand wurde nicht hochgeladen. Der private Testdienst ist inzwischen
installiert; Windows-Zugriff, Anmeldung, fiktiver Kunden-/Projekt-/Berichtsablauf,
Unterschrift und PDF sind bestätigt. Eine manuelle Datenbanksicherung war
erfolgreich. Auch nach einem VM-Neustart konnte der Nutzer die Testdaten und
das PDF wieder öffnen. Die Einzelbelege stehen in
[ABNAHME.md](deploy/hetzner/ABNAHME.md). Die vorhandene App bleibt lokal nutzbar.

## Nächste Stufe: öffentliche API und HTTPS

Konto, VM und privater systemd-Testdienst sind eingerichtet und müssen nicht
erneut angelegt werden. Eigenes Dienstkonto, automatischer Start und manuell
ausgelöste konsistente Sicherung sind auf Hetzner bestätigt. Siehe
[Anleitung](deploy/hetzner/README.md). Der Zugriff erfolgt über einen SSH-Tunnel;
die öffentliche API ist damit noch nicht freigegeben. Wix-DNS-Zugriff
ist inzwischen bestätigt: `office.smartplan-hofmann.de` zeigt per A-Eintrag auf
`116.203.43.69`; die Windows-DNS-Abfrage vom 22. Oktober bestätigt das.
Website und E-Mail verbleiben bei den bestehenden Anbietern.

Das [separate HTTPS-Einrichtungspaket](deploy/hetzner/https/README.md) liefert
zunächst nur eine statische Seite, ohne Verbindung zur privaten API. Nach der
DNS-Prüfkorrektur `f1e8f9c` hat der Nutzer es installiert: systemd meldet
`active (running)`, und der Browser zeigt die Seite über HTTPS ohne sichtbare
Zertifikatswarnung. Diese Nachweise liegen vom 22. Oktober vor. Produktions-API,
Datenhaltung, MFA und darauf konfigurierte Apps bleiben weitere Entwicklung.
Der nächste [Online-Pilot 0.5](deploy/hetzner/online/README.md) enthält inzwischen
eine separate PostgreSQL-Datenhaltung, versionierte Flask/Gunicorn-API und
Authenticator-Anmeldung. Code und lokale Prüfungen sind vorbereitet;
Serverinstallation, öffentlicher API-Zugriff und Windows-Online-Paket sind
noch getrennt am Nutzer-System abzunehmen. Eine echte Datenübernahme bleibt offen.
Zugangsdaten gehören ausschließlich in geeignete sichere Einstellungen.
Ob Konto-2FA bereits aktiviert ist, wurde nicht gesondert bestätigt.

## Bestätigte Auswahl des Testservers

| Einstellung | Vorgesehener Wert | Warum |
| --- | --- | --- |
| Produkt | Hetzner Cloud, virtuelle Maschine mit geteilter CPU | Kleiner Einstieg ohne dedizierten Server |
| Standort | Nürnberg, Deutschland | Gewählter Datenstandort |
| Architektur | CAX11, ARM64 (Ampere) | Backend-Pakete und Tests auf dem echten ARM-Server geprüft |
| Betriebssystem | Ubuntu 24.04 LTS | Gepflegtes Linux-System mit Python 3.12 |
| Größe | 2 vCPU, 4 GB RAM, 40 GB SSD | Ausgangspunkt für wenige Nutzer; Last und Speicherverbrauch noch zu prüfen |
| Netz | IPv4 und IPv6; SSH auf Verwaltungs-IP beschränkt | Firewall angewendet; keine öffentliche App/API eingerichtet |
| Servername | `smartplan-test` | Getrennte erste Testumgebung |
| Weitere Produkte | Zunächst keine Load Balancer, Kubernetes oder zusätzlichen Datenbankserver | Für den ersten Test nicht erforderlich |

Die Bestellübersicht zeigte monatlich **5,99 Euro netto** für CAX11, **1,20 Euro
netto** für Backups und **0,50 Euro netto** für IPv4: insgesamt **7,69 Euro netto
bzw. 9,15 Euro mit 19 Prozent Umsatzsteuer**. Der Nutzer hat den Server bestellt.
Ein separates Sicherungsziel und gegebenenfalls eine Domain kommen hinzu.
Die vorher genannten **10–20 Euro brutto pro Monat** bleiben ein grober
Planungsrahmen für die gesamte Infrastruktur, keine garantierte Gesamtrechnung.
Einrichtung, laufende Betreuung und eine mögliche Apple-Mitgliedschaft sind
darin nicht enthalten. Hetzner Cloud ist ein selbst verwalteter Server:
Systemupdates, Betrieb und Kontrolle der Sicherungen brauchen eine zuständige Person.

Vor weiteren Bestellungen werden Tarif, monatlicher Bruttopreis, Sicherungsziel und
weitere Leistungen zusammengefasst. Falls die Summe den genannten
Planungsrahmen überschreitet, wird zuerst die Auswahl angepasst oder der höhere
Betrag geklärt. Die Anbieterwahl allein ist keine Bestätigung eines weiteren unbekannten
Tarifs. Die Abrechnung neuer Angebote ist vorab zu prüfen; ein laufender
Cloud-Server kann auch im ausgeschalteten Zustand Kosten verursachen.

## Technische Prüfung des vorhandenen Standes

| Vorhanden | Noch vor öffentlichem Betrieb umzusetzen |
| --- | --- |
| Lokale Python-API auf `127.0.0.1:8765` | Produktionsgeeignete API-Laufzeit mit Zeit-/Anfragelimits und geordnetem Herunterfahren |
| SQLite-Schema 1 mit Konten, Kunden, Projekten und PDF-Bytes | Gemäß Betriebsplanung PostgreSQL-Anbindung, Migration und geprüfte parallele Änderungen |
| Passwortanmeldung, Rollen und Projektzuordnung | Festgelegtes MFA-Verfahren für gemeinsamen Betrieb und Schutz gegen wiederholte Anmeldeversuche |
| App akzeptiert entfernte Adressen ausschließlich über HTTPS | Eigene erreichbare HTTPS-Adresse, Zertifikat und darauf konfiguriertes Windows-Paket |
| Sicherungsdienst auf Hetzner erfolgreich, Timer registriert; Wiederherstellung synthetischer Daten automatisiert geprüft | Getrenntes verschlüsseltes Ziel und Wiederherstellung einer tatsächlichen Serversicherung |
| `/health` meldet den lokalen Prozess | Bereitschaftsprüfung mit echtem Datenbankzugriff und Überwachung |

Der aktuelle `backend/server.py` ist ausdrücklich ein Entwicklungsserver.
Er wird weder an `0.0.0.0` gebunden noch durch eine Firewall-Freigabe zum
öffentlichen Server erklärt. Die lokale `Office`-Klasse benutzt eine SQLite-
Verbindung; mehrere API-Prozesse erfordern eine geeignete Datenhaltung.
Die App-Adresse ist aktuell beim Build über `API_URL` festgelegt. Ein gekaufter
Server verbindet daher das bestehende Windows-Paket oder das iPhone noch nicht.

## Reihenfolge bis zur ersten Online-Abnahme

1. Konto, Testserver und privater Dienst sind eingerichtet. Grundinstallation,
   ARM-Tests, privater Windows-Ablauf, Sicherung und VM-Wiederanlauf sind bestätigt.
2. Produktions-API und Datenübernahme entwickeln und unabhängig vom echten
   Kundendatenbestand testen. Die übrigen Lieferpakete stehen in
   [BETRIEB_UND_IPHONE.md](BETRIEB_UND_IPHONE.md).
3. Server mit SSH-Schlüssel und Firewall vorbereiten: Verwaltung nur aus
   festgelegten Zugängen, öffentlich später ausschließlich HTTP/HTTPS;
   Datenbank- und interne API-Ports bleiben geschlossen.
4. DNS, Installation des separaten HTTPS-Pakets und Seitenaufruf über HTTPS
   sind bestätigt. Die Einrichtungsseite allein bestätigt noch keinen
   öffentlichen App-Betrieb.
5. Dienste mit automatischem Neustart, eingeschränktem Dienstkonto, geschützten
   Schlüsseln, Systemupdates und Betriebsüberwachung einrichten.
6. Zuerst fiktive Daten verwenden. Anmeldung, Rollen, Projektzugriff, Unterschrift,
   PDF-Ausgabe und Neustart über die echte HTTPS-Adresse prüfen.
7. Sicherung auf einem vom App-Server getrennten Ziel und Wiederherstellung in
   einer frischen Testdatenbank prüfen. Server-Snapshots allein reichen dafür
   nicht. Aufbewahrung, Kosten und Schlüsselzugriff vorab festlegen.
8. Erst danach eine überprüfte Kopie der Windows-Sicherung übernehmen. Die aktive
   Quelle kommt aus `%LOCALAPPDATA%\SmartplanOffice\start-config.json`, auch nach
   einer lokalen Wiederherstellung. Konten, Beziehungen und PDF-Bytes vergleichen;
   alte Sitzungen verwerfen. Die lokale Quelle bleibt erhalten. Beim Umstieg
   gibt es einen festgelegten Schreibstopp und anschließend nur einen aktiven
   Datenbestand, damit keine voneinander abweichenden Berichte entstehen.

Vor echten Kundendaten werden auch der Auftragsverarbeitungsvertrag und die
Datenstandorte von Server und Sicherungsziel geprüft. Ein deutscher Serverstandort
allein bestätigt keine vollständige Datenschutz- oder GoBD-Konformität.

## Separat verbleibende Schritte

Die iPhone-Installation braucht weiterhin einen geeigneten Verteilungsweg und
Apple-Signierung. Ein funktionierender Windows-Serverzugang bestätigt diese
Installation nicht. OneDrive ist eine separate Verbindung und ersetzt die
Serverdatenbank oder deren Sicherung nicht. Konto und VM bestehen bereits;
Domain und weitere Konten werden mit den jeweils vorhandenen Zugängen verbunden.
