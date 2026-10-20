# Smartplan bei Hetzner vorbereiten

Stand: 20. Oktober 2026. Der Nutzer hat Hetzner als Hosting-Anbieter gewählt.
Ein Hetzner-Konto besteht noch nicht. Es wurde kein Server bestellt und kein
Kundendatenbestand hochgeladen. Die vorhandene Windows-App bleibt lokal nutzbar.

## Dein nächster Schritt

1. [Hetzner Console](https://console.hetzner.com/) öffnen und ein Konto anlegen.
2. E-Mail-Adresse bestätigen und die von Hetzner verlangte Kontoprüfung abschließen.
3. Zwei-Faktor-Anmeldung für das Hetzner-Konto einrichten.
4. Nach der Anmeldung zur Cloud-Konsole wechseln. Zunächst keinen Server bestellen.

Für die anschließende Auswahl genügt ein Bildschirmfoto der angebotenen
Servertypen mit Preisen. Zahlungsdaten, Kontonummern, Passwörter, Tokens und
private Schlüssel vorher ausblenden. Zugangsdaten werden ausschließlich in
dafür vorgesehenen sicheren Einstellungen hinterlegt.

## Vorgesehene Auswahl für einen ersten Testserver

| Einstellung | Vorgesehener Wert | Warum |
| --- | --- | --- |
| Produkt | Hetzner Cloud, virtuelle Maschine mit geteilter CPU | Kleiner Einstieg ohne dedizierten Server |
| Standort | Deutschland, je nach verfügbarem Angebot Nürnberg oder Falkenstein | Gewählter Datenstandort |
| Architektur | x86-64 (Intel/AMD) | Einheitliche Python-/PDF-Laufzeit für den ersten Server |
| Betriebssystem | Ubuntu 24.04 LTS | Gepflegtes Linux-System mit Python 3.12 |
| Größe | Zunächst 2 vCPU, 4 GB RAM, mindestens 40 GB SSD | Ausgangspunkt für wenige Nutzer; Last und Speicherverbrauch noch zu prüfen |
| Netz | Öffentliche IPv4 und IPv6, sofern im gewählten Tarif angeboten | Erreichbarkeit für Büro- und Mobilfunknetze |
| Servername | `smartplan-test` | Getrennte erste Testumgebung |
| Weitere Produkte | Zunächst keine Load Balancer, Kubernetes oder zusätzlichen Datenbankserver | Für den ersten Test nicht erforderlich |

Die tatsächlichen Tarife, Verfügbarkeit, Backup- und IPv4-Aufpreise müssen in
der Konsole vor dem Bestellschritt überprüft werden. Die vorher genannten
**10–20 Euro brutto pro Monat** sind ein grober Planungsrahmen für Server,
Sicherungen und gegebenenfalls Domain, kein verifizierter Hetzner-Tarif.
Einrichtung, laufende Betreuung und eine mögliche Apple-Mitgliedschaft sind
darin nicht enthalten. Hetzner Cloud ist ein selbst verwalteter Server:
Systemupdates, Betrieb und Kontrolle der Sicherungen brauchen eine zuständige Person.

Vor Bestellung werden Tarif, monatlicher Bruttopreis, IPv4, Sicherungsziel und
weitere gebuchte Leistungen zusammengefasst. Falls die Summe den genannten
Planungsrahmen überschreitet, wird zuerst die Auswahl angepasst oder der höhere
Betrag geklärt. Die Anbieterwahl allein ist keine Bestätigung eines unbekannten
Tarifs. Die Abrechnung des gewählten Angebots ist vorab zu prüfen; ein laufender
Cloud-Server kann auch im ausgeschalteten Zustand Kosten verursachen.

## Technische Prüfung des vorhandenen Standes

| Vorhanden | Noch vor öffentlichem Betrieb umzusetzen |
| --- | --- |
| Lokale Python-API auf `127.0.0.1:8765` | Produktionsgeeignete API-Laufzeit mit Zeit-/Anfragelimits und geordnetem Herunterfahren |
| SQLite-Schema 1 mit Konten, Kunden, Projekten und PDF-Bytes | Gemäß Betriebsplanung PostgreSQL-Anbindung, Migration und geprüfte parallele Änderungen |
| Passwortanmeldung, Rollen und Projektzuordnung | Festgelegtes MFA-Verfahren für gemeinsamen Betrieb und Schutz gegen wiederholte Anmeldeversuche |
| App akzeptiert entfernte Adressen ausschließlich über HTTPS | Eigene erreichbare HTTPS-Adresse, Zertifikat und darauf konfiguriertes Windows-Paket |
| Lokale Sicherung und Wiederherstellung getestet | Automatischer Sicherungsplan, getrenntes verschlüsseltes Ziel und überprüfte Wiederherstellung |
| `/health` meldet den lokalen Prozess | Bereitschaftsprüfung mit echtem Datenbankzugriff und Überwachung |

Der aktuelle `backend/server.py` ist ausdrücklich ein Entwicklungsserver.
Er wird weder an `0.0.0.0` gebunden noch durch eine Firewall-Freigabe zum
öffentlichen Server erklärt. Die lokale `Office`-Klasse benutzt eine SQLite-
Verbindung; mehrere API-Prozesse erfordern eine geeignete Datenhaltung.
Die App-Adresse ist aktuell beim Build über `API_URL` festgelegt. Ein gekaufter
Server verbindet daher das bestehende Windows-Paket oder das iPhone noch nicht.

## Reihenfolge bis zur ersten Online-Abnahme

1. Konto und Angebot klären. Vor einer Bestellung den genauen Gesamtpreis sehen.
2. Produktions-API und Datenübernahme entwickeln und unabhängig vom echten
   Kundendatenbestand testen. Die übrigen Lieferpakete stehen in
   [BETRIEB_UND_IPHONE.md](BETRIEB_UND_IPHONE.md).
3. Server mit SSH-Schlüssel und Firewall vorbereiten: Verwaltung nur aus
   festgelegten Zugängen, öffentlich später ausschließlich HTTP/HTTPS;
   Datenbank- und interne API-Ports bleiben geschlossen.
4. Eine eigene Subdomain mit gültigem HTTPS-Zertifikat einrichten, beispielsweise
   `office.deine-domain.de`. Das ist ein Platzhalter. Eine vorhandene Domain kann
   weiterverwendet werden; die Website und E-Mail müssen dafür nicht umziehen.
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
Serverdatenbank oder deren Sicherung nicht. Hetzner-Konto, Server und Domain
werden erst eingerichtet beziehungsweise verbunden, wenn die jeweiligen
Zugänge vorhanden sind.
