# Privater Smartplan-Testdienst auf Hetzner

Diese Stufe verwendet den bestehenden lokalen Entwicklungsserver ausschließlich
auf `127.0.0.1:8765`. Sie dient zum Testen von Neustart, privatem Windows-Zugriff
über einen SSH-Tunnel und konsistenter Datensicherung. Öffentliche Produktions-API,
PostgreSQL, MFA, HTTPS und die echte iPhone-Installation bleiben eigene Lieferpakete.
Es werden weder öffentliche Ports geöffnet noch echte Windows-Daten übernommen.

Stand 21. Oktober 2026: Der Nutzer hat Dienststart, privaten Windows-Ablauf,
manuelle Sicherung und Datenzugriff nach einem VM-Neustart bestätigt. Die
Einzelbelege und verbleibenden Schritte stehen in [ABNAHME.md](ABNAHME.md).
Die Installationsanleitung darunter bleibt für Wiederholung und neue Testinstanzen
erhalten; sie muss auf dem bereits eingerichteten Server nicht erneut ausgeführt werden.

## Voraussetzungen und Installation

Ziel: Ubuntu 24.04 LTS, ARM64 oder x86-64 mit systemd. Der root-eigene Checkout
liegt unter `/opt/smartplan-test`, die bereits geprüften Python-Pakete in
`/opt/smartplan-test/backend/.venv`. Auf dem Nutzer-ARM-Server wurden die bisherigen
32 Backend-Fälle ausgeführt: 31 bestanden, ein Windows-Fall übersprungen.

Im bestehenden SSH-Serverfenster nacheinander:

```bash
git -C /opt/smartplan-test pull --ff-only
```

```bash
bash /opt/smartplan-test/deploy/hetzner/install-pilot.sh
```

Das Installationsskript prüft Zielsystem, Abhängigkeiten, fremde Portbelegung,
abweichende bestehende Units und das Dienstkonto. Es erstellt `smartplan-pilot`
ohne Login-Shell, das private Datenverzeichnis `/var/lib/smartplan-pilot` und
die systemd-Units aus diesem Ordner. Es überschreibt keine abweichende Unit und
stoppt keinen fremden Prozess. Eine Wiederholung startet einen bereits laufenden
eigenen Dienst nicht neu. Der gemeinsame lokale Windows-Datenbestand bleibt erhalten.

Der Dienst wird beim Booten gestartet und bei Fehlern erneut versucht; nach fünf
Fehlstarts in einer Minute greift die systemd-Startbegrenzung. Er läuft ohne root,
mit schreibgeschütztem System und privatem temporärem Verzeichnis. Dauerhafte
App-Schreibzugriffe sind auf das eigene systemd-Datenverzeichnis beschränkt.
Der Datenordner ist nur für das Dienstkonto und root zugänglich (Modus 0700).

Die Installation prüft den tatsächlichen HTTP-Prozess: `/health` muss `status=ok`
und `launch_id=smartplan-private-pilot` liefern, `/api/projects` ohne Anmeldung
muss mit 401 antworten. Der historische Backend-Versionswert bleibt
`0.2.0-development`; er ist keine Produktionsfreigabe oder Prüfung der Datenbank.
Es gibt weiterhin kein automatisch angelegtes Benutzerkonto.

## Status und Diagnose auf dem Server

```bash
systemctl status smartplan-pilot --no-pager --full
```

```bash
curl --fail --silent --show-error http://127.0.0.1:8765/health
```

```bash
ss -ltnp 'sport = :8765'
```

Die Listen-Adresse muss `127.0.0.1:8765` sein. Die Firewall-Freigabe für SSH
bleibt auf die Verwaltungsadresse beschränkt; bei einem Wechsel der öffentlichen
Verwaltungs-IP muss diese Regel über die Hetzner-Konsole angepasst werden.

```bash
journalctl -u smartplan-pilot -n 40 --no-pager
```

In dieser Entwicklungsumgebung läuft systemd nicht als PID 1. Hier können daher
die Unit-Dateien statisch geprüft und der echte nicht privilegierte Startprozess
mit temporären Testdaten getestet werden. Der tatsächliche systemd-Start und ein
Serverneustart werden getrennt auf dem Hetzner-Server abgenommen.

## Eigenes Pilotkonto anlegen

Erst nach dem erfolgreichen Dienststart ein neues Testkonto einrichten. Der
Pilotdatenbestand ist von der lokalen Windows-Datenbank getrennt. Dafür eine
selbst gewählte E-Mail anstelle von `pilot@example.test` verwenden. Das Passwort
wird verdeckt abgefragt und gehört weder in einen Befehl noch in den Chat.

Während der Initialisierung den eigenen Pilotdienst anhalten:

```bash
systemctl stop smartplan-pilot
```

```bash
runuser --pty -u smartplan-pilot -- env OFFICE_DATA_DIR=/var/lib/smartplan-pilot /opt/smartplan-test/backend/.venv/bin/python /opt/smartplan-test/backend/server.py --init-owner pilot@example.test
```

```bash
systemctl start smartplan-pilot
```

Den letzten Startbefehl auch nach einer abgebrochenen Passworteingabe ausführen.
Ein bereits vorhandenes Geschäftsführungskonto wird vom Initialisierer abgewiesen
und nicht überschrieben. Danach nur fiktive Kunden, Projekte und Berichte anlegen.

## Privater Windows-Test ohne Änderung der lokalen Datenbank

1. Lokale App und den lokalen `Starten.cmd`-Starter regulär schließen; dadurch
   kann dessen abschließende Sicherung laufen. Port 8765 auf Windows muss frei sein.
2. In einem neuen Windows-PowerShell-Fenster einen Tunnel öffnen. `SERVER_IP`
   durch die öffentliche IPv4-Adresse aus der eigenen Hetzner-Konsole ersetzen:

```powershell
ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -L 127.0.0.1:8765:127.0.0.1:8765 -i "$env:USERPROFILE\.ssh\smartplan_hetzner" root@SERVER_IP
```

3. Dieses Fenster bleibt geöffnet. In einem zweiten Windows-PowerShell-Fenster:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
```

Der Marker muss `smartplan-private-pilot` lauten. So wird der Serverpilot von
einem versehentlich noch laufenden lokalen Backend unterschieden.

4. Die vorhandene `smartplan_office.exe` direkt aus dem entpackten Windows-Paket
   öffnen, **nicht** `Starten.cmd`, denn dieser würde einen lokalen Server starten.
   Mit dem getrennt eingerichteten Pilotkonto anmelden, einen klar bezeichneten
   fiktiven Kunden, ein Projekt und einen unterschriebenen Bericht testen.
5. App schließen und Tunnel mit Strg+C beenden. Anschließend ist der gewöhnliche
   lokale Betrieb über den bisherigen Starter wieder möglich.

Dieser Test benutzt die verschlüsselte SSH-Verbindung. Er ist kein öffentlicher
HTTPS-Zugang und kein Nachweis des gemeinsamen Windows-/iPhone-Betriebs.

Für den bestätigten VM-Neustarttest wurde stattdessen die kombinierte Verbindung
verwendet: derselbe SSH-Befehl ohne `-N` öffnet zugleich die interaktive
Serverkonsole und den App-Tunnel. Das Fenster bleibt geöffnet. Es dürfen nicht
beide Varianten gleichzeitig denselben lokalen Port 8765 belegen.

Bei den Windows-PowerShell-/SSH-Sitzungen erschienen beim Einfügen teilweise
Steuerzeichen `^[[200~`. `bind 'set enable-bracketed-paste off'` wurde in der
betroffenen Server-Bash von Hand eingegeben und behob das Problem für diese
Sitzung. Ein Prompt-Zeichen `#` wird nicht als Teil eines Befehls eingegeben.

## Lokale Sicherungen und Wiederherstellung

Vor jedem Dienststart wird eine vorhandene SQLite-Datenbank mit dem bestehenden
konsistenten Backup-Werkzeug gesichert. Zusätzlich läuft täglich ein systemd-Timer,
mit zufälliger Verzögerung bis 15 Minuten und Nachholen versäumter Termine.
Die Uhrzeit richtet sich nach der Server-Zeitzone. Dateien und SHA-256-Prüfsummen
liegen in `/var/lib/smartplan-pilot/backups`; die Dateien haben Modus 0600.
Ein Start vor der ersten Datenbankanlage erzeugt keine leere Sicherung.

```bash
systemctl list-timers smartplan-pilot-backup.timer --no-pager
```

```bash
systemctl start smartplan-pilot-backup.service
```

Es gibt in dieser Teststufe keine automatische Löschung alter Sicherungen;
Speicherverbrauch kontrollieren. Ein Fehler erscheint im jeweiligen systemd-
Status/Journal; automatische Benachrichtigungen sind noch nicht eingerichtet.
Diese Kopien liegen auf derselben VM. Die ausgewählten Hetzner-Backups und ein
zusätzliches getrenntes, verschlüsseltes Sicherungsziel sind davon zu unterscheiden.
Das getrennte Ziel und die Wiederherstellung des echten Nutzerdatenbestands bleiben offen.

Für einen manuellen Wiederherstellungstest eine Sicherung samt Prüfsumme auswählen,
die Prüfsumme vergleichen und `backend/restore.py` unter dem Dienstkonto mit einem
**neuen** Zielpfad in `/var/lib/smartplan-pilot` ausführen. Die aktive Datenbank
wird nicht überschrieben. Das bestehende Werkzeug löscht Sitzungen in der Kopie.
Die automatische Start-/Backup-Prüfung verwendet dazu ausschließlich temporäre
fiktive Daten; sie prüft Beziehungen und byteidentische unterschriebene PDFs.

## Änderungen am Pilotcode und Rückbau

Kein automatisches `git pull` in einem laufenden Dienst: Für einen späteren
Codewechsel zuerst eine geprüfte Sicherung erstellen, den eigenen Dienst
anhalten, den konkreten freigegebenen Stand aktualisieren und den Dienst danach
wieder starten und prüfen. Das Installationsskript ist kein Upgrade-Werkzeug.

```bash
systemctl disable --now smartplan-pilot-backup.timer
```

```bash
systemctl stop smartplan-pilot-backup.service
```

```bash
systemctl disable --now smartplan-pilot.service
```

Dies hält nur die eigenen Pilotdienste an. Datenverzeichnis, Sicherungen und
Hetzner-Ressourcen bleiben erhalten; die Serverkosten laufen weiter.
