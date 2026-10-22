# HTTPS als eigener Einrichtungsschritt

Stand 22. Oktober 2026: Der Nutzer hat bei Wix den A-Eintrag
`office.smartplan-hofmann.de` → `116.203.43.69` gespeichert. Die Windows-Abfrage
`Resolve-DnsName` bestätigt diese Zuordnung. Die drei bisherigen Wix-A-Einträge
der Hauptdomain, `www`, Google-Workspace-Mail und Nameserver bleiben erhalten.

Dieses Paket veröffentlicht ausschließlich eine statische Einrichtungsseite.
Es enthält **keinen Reverse-Proxy** zum privaten Entwicklungsserver. `/api`,
`/auth`, `/oauth` samt Unterpfaden sowie `/health` und `/ready` antworten mit
503 und `{"status":"setup"}`. Andere unbekannte Pfade erhalten 404. Es gibt
noch keine öffentliche Anmeldung und kein neues Windows-/iPhone-App-Paket.

## Installation auf dem vorhandenen Server

Ziel ist derselbe Ubuntu-24.04-Server, Checkout `/opt/smartplan-test` als root.
Die bestehende Pilotinstallation und ihre Daten werden nicht geändert.

1. In der Hetzner-Firewall `firewall-1` zusätzlich zwei **eingehende** Regeln
   erstellen: TCP **80** und TCP **443**, jeweils `Any IPv4` und `Any IPv6`.
   TCP 22 bleibt auf die eigene Verwaltungs-IP beschränkt. Port 8765 erhält
   keine öffentliche Freigabe. Ausgehende Verbindungen bleiben erlaubt.
2. Im SSH-Fenster mit Prompt `root@smartplan-test:~#` nacheinander:

```bash
git -C /opt/smartplan-test pull --ff-only
```

```bash
bash /opt/smartplan-test/deploy/hetzner/https/install-https.sh
```

Das Skript prüft Zielsystem, DNS-Zuordnung aller A-/AAAA-Antworten zur VM,
Portbelegung und vorhandene Dateien/Konten. Es beendet keine fremden Dienste
und überschreibt keine bestehende HTTPS-Installation. Bei einem Abbruch nach
Teilschritten zuerst die Ursache prüfen; nicht Dateien auf Verdacht löschen.

Caddy **2.11.7** wird aus dem offiziellen GitHub-Release geladen. Die SHA-512
der ARM64- und AMD64-Archive sind im Downloadskript festgeschrieben und stammen
aus `caddy_2.11.7_checksums.txt` des Releases. Bei einem späteren Versionswechsel
neue Prüfsummen und Tests prüfen; kein automatischer Binärdownload beim Booten.

Der Webdienst läuft als eigenes Konto `smartplan-https` ohne Login-Shell.
Nur die Fähigkeit zum Binden niedriger Ports wird vergeben; das System ist
schreibgeschützt. Zertifikate liegen im privaten Datenverzeichnis
`/var/lib/smartplan-https` (0700). Der Verwaltungsendpunkt ist ein Unix-Socket
unter `/run/smartplan-https` (0700). Es gibt keinen HTTP-Adminport. Das separate
Pilot-Datenverzeichnis bleibt für diesen Webnutzer unzugänglich.

## Tatsächliche HTTPS-Abnahme

Der erfolgreiche systemd-Start bestätigt noch keine Zertifikatsausstellung.
Caddy beantragt und erneuert das Zertifikat automatisch; korrekte DNS-Antworten,
öffentliche Ports 80/443 und ausgehendes HTTPS sind dafür erforderlich.

In **Windows PowerShell**, nach kurzer Wartezeit:

```powershell
Invoke-WebRequest https://office.smartplan-hofmann.de -UseBasicParsing | Select-Object StatusCode
```

Erwartet: 200 ohne Zertifikatswarnung. Die Adresse zusätzlich im Browser öffnen:
„Der Onlinezugang wird vorbereitet“. HTTP soll auf HTTPS umleiten.
`https://office.smartplan-hofmann.de/health` muss in dieser Stufe **503** liefern.
Es wird niemals die Prozess-Gesundheitsmeldung des privaten Piloten veröffentlicht.
Keine Zertifikatsprüfung umgehen und kein selbst signiertes Zertifikat auf dem
Nutzergerät installieren. Die öffentliche Domain verwendet reguläre ACME-Zertifikate.

Auf dem Server bei Problemen:

```bash
journalctl -u smartplan-https -n 40 --no-pager
```

```bash
systemctl status smartplan-https --no-pager --full
```

Zum vorläufigen Abschalten nur dieses Einrichtungspakets:

```bash
systemctl disable --now smartplan-https.service
```

Zertifikate und Pilotdaten bleiben dabei erhalten. Die öffentliche API mit
geeigneter Laufzeit, PostgreSQL/Migration, MFA, App-Konfiguration und gemeinsamer
Geräteabnahme ist weiterhin ein eigenes Lieferpaket.

## Entwicklungsprüfung

Ohne root eine frische temporäre Ablage verwenden:

```bash
smartplan_caddy_test=$(mktemp -d)
bash deploy/hetzner/https/fetch-caddy.sh "$smartplan_caddy_test"
SMARTPLAN_CADDY_BINARY="$smartplan_caddy_test/caddy" python3 deploy/hetzner/https/test_https.py
```

Der Test startet den echten geprüften Caddy-Prozess auf lokalen hohen Ports.
Die separate DNS-Prüfung wird mit `python3 -m unittest discover -s deploy/hetzner/https -p test_dns.py -v`
geprüft: unvollständige Netzwerkdatensätze dürfen keinen Absturz verursachen;
fehlende lokale Adressen, fremde DNS-Ziele und abweichende AAAA-Antworten
werden weiterhin abgewiesen.
Nur im Test werden Domain/Pfade/Ports angepasst und eine interne Test-CA benutzt.
Der HTTPS-Client vertraut explizit deren Root-Zertifikat und prüft den Hostnamen;
eine Anfrage ohne dieses Vertrauen muss scheitern. Geprüft werden die statische
Seite, HTTP-Weiterleitung, Header, 404 und die Sperre der API-Endpunkte auch bei
POST. Weder System-Vertrauensspeicher noch App-Daten werden verändert. Zusätzlich
werden Bash und systemd-Unit statisch geprüft. Ein tatsächlicher systemd-Start
und ein öffentliches ACME-Zertifikat müssen am Nutzer-Server bestätigt werden.
