# Gemeinsamer Online-Pilot 0.5

Diese Stufe ergänzt die vorhandene HTTPS-Einrichtungsseite um eine versionierte
API unter `/api/v1`, PostgreSQL 16 und Passwort plus Authenticator-Code. Das
separate Windows-Paket enthält die Serveradresse und benötigt keinen SSH-Tunnel.
Zunächst ausschließlich fiktive Daten verwenden. Die Einrichtung auf der echten
VM und die Windows-Anmeldung müssen nach den automatisierten Prüfungen separat
abgenommen werden. Eine fertige iPhone-Verteilung und Produktionsfreigabe sind
damit nicht verbunden.

Aktueller Abnahmestand: Der Nutzer hat Installation, getrenntes Online-Konto und
HTTPS-Aktivierung am 22. Oktober bestätigt. Der öffentliche Projektabruf ohne
Anmeldung liefert wie vorgesehen 401. Der zugehörige
[CI-Lauf 39835146915](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/39835146915)
ist einschließlich beider nativen Builds erfolgreich. Windows-Online-Anmeldung,
Authenticator-Einrichtung und Fachablauf auf dem Nutzer-PC folgen noch. Die
Erstinstallation und Aktivierung auf diesem Server nicht wiederholen.

## Trennung vom bisherigen Test

- Der SQLite-Pilot auf `127.0.0.1:8765` und `/var/lib/smartplan-pilot` bleibt erhalten.
- Der Online-Pilot läuft als `smartplan-online` auf `127.0.0.1:8766`. Datenbank:
  `smartplan_online`, eigene Rolle gleichen Namens wie das Dienstkonto.
- PostgreSQL verwendet den Unix-Socket mit Peer-Anmeldung. Kein Datenbankpasswort
  wird in Befehle, Quelltext oder Chat geschrieben. Keine Freigabe von 5432/8766.
- Root-eigener Code und Venv liegen als separate Kopie unter `/opt/smartplan-online`.
  Ein späteres `git pull` ersetzt diese laufende Kopie nicht.
- Das Online-Konto wird separat angelegt. Keine automatische Übernahme lokaler
  Konten, Kunden, Sitzungen, OneDrive-Tokens oder echter Windows-Daten.

## Installation, Konto, Aktivierung

Auf dem vorhandenen Ubuntu-24.04-Server im SSH-Fenster als root. HTTPS muss
bereits mit der ursprünglichen isolierten Konfiguration laufen. Die Installation
ist einmalig und verweigert vorhandene Zielpfade/Konten/Units. Bei einem Fehler
nach Teilschritten erst die Ursache prüfen; nicht Dateien oder Datenbanken löschen.

```bash
git -C /opt/smartplan-test pull --ff-only
```

```bash
bash /opt/smartplan-test/deploy/hetzner/online/install-online.sh
```

Das installiert PostgreSQL 16 und dessen Client auf derselben bereits bestellten
VM. Es wird kein weiterer Server oder kostenpflichtiger Dienst gebucht. Die
vorhandene HTTPS-Weiterleitung wird in diesem Schritt noch nicht geändert.
Zielsystem, saubere Quellen, Ports, bestehende Installationen, Datenbankrolle und
Loopback-Bindung werden geprüft. Bestehende fremde Dienste werden nicht gestoppt.

Danach mit der eigenen E-Mail ein neues Online-Testkonto anlegen:

```bash
bash /opt/smartplan-test/deploy/hetzner/online/manage-online.sh init-owner info@smartplan-hofmann.de
```

Das Passwort verdeckt eingeben und wiederholen. Mindestens zwölf Zeichen.
Passwort, spätere Authenticator-QR-Codes und Wiederherstellungscodes nicht in den
Chat oder Screenshots übernehmen. Es gibt kein Standardkonto.

Ohne weiteres `git pull` zwischen diesen Schritten die geprüfte Kopie aktivieren:

```bash
bash /opt/smartplan-test/deploy/hetzner/online/activate-online.sh
```

Das prüft Code-Stand, Datenbank, eigenes Konto und die bisherige Caddy-Konfiguration
und führt vor der Umschaltung eine lokale PostgreSQL-Sicherung aus.
Nur `/api/v1/*`, `/health` und `/ready` werden auf **8766** geleitet. Der alte
Entwicklungsserver wird nicht öffentlich weitergeleitet. Andere `/api`- und
OAuth-Pfade bleiben gesperrt. Vorherige Konfiguration wird gesichert; bei einem
fehlgeschlagenen Reload oder öffentlichen 401-Test wird sie wiederhergestellt.
Der HTTPS-Verwaltungssocket bleibt privat. Die Browser-Hinweisseite enthält keine
Web-Anmeldung; angemeldet wird in der nativen Windows-App.

## Windows-Anmeldung

In GitHub Actions das Artefakt **Smartplan-Office-Windows-Online-Pilot** des
passenden erfolgreichen Windows-Builds herunterladen. Vollständig in einen neuen
Ordner entpacken und `smartplan_office.exe` direkt öffnen. Die Anmeldung zeigt
„Online-Pilot · office.smartplan-hofmann.de“. Das lokale Paket bleibt separat.

Bei der ersten Anmeldung mit dem neuen Online-Testkonto den QR-Code in einer
Authenticator-App scannen, den aktuellen sechsstelligen Code bestätigen und die
zehn einmal angezeigten Wiederherstellungscodes sicher aufbewahren. Anschließend
erfolgt die Anmeldung mit Passwort und aktuellem Code. Ein bereits verwendeter
Zeitcode wird abgewiesen; nötigenfalls den nächsten 30-Sekunden-Code abwarten.
Jeder Wiederherstellungscode kann einmal statt des Zeitcodes verwendet werden.
Sitzungstokens bleiben nur im App-Speicher; keine automatische Daueranmeldung.

Abnahme: fiktiven Kunden und Projekt anlegen, Techniker zuweisen, Bericht
unterzeichnen, PDF öffnen. Projektentzug sperrt den Zugriff, Kontosperrung
widerruft Sitzungen. Danach VM-Neustart und erneuten Zugriff prüfen. Erst die
tatsächliche Geräteprüfung bestätigt die Bereitstellung auf diesem Server.

## Datenhaltung und Anmeldeschutz

Die bisherigen Domänenregeln werden für SQLite und PostgreSQL gemeinsam verwendet.
Migration erfolgt explizit; API-Anfragen ändern kein Schema. Transaktionen mit
verschachtelten Savepoints und einer PostgreSQL-Transaktionssperre serialisieren
Änderungen in dieser kleinen Pilotstufe über mehrere Worker. Jede Fachanfrage
prüft den aktuellen Sitzungsstatus und die Rechte innerhalb derselben Transaktion.
Dies ist kein Lastnachweis für große Nutzerzahlen; die Sperre begrenzt den Durchsatz.

Flask läuft unter zwei Gunicorn-Workern mit begrenzten Threads, Anfragekopfgrößen,
Zeitlimits und Worker-Wiederanlauf. JSON-Nutzdaten sind auf 1 MB begrenzt. Nur der
lokale HTTPS-Proxy liefert vertrauenswürdige Weiterleitungsheader. HTTP oder falsche
Hostnamen werden an der API abgewiesen. Es gibt keine Request-Logs mit Passwörtern,
Tokens oder OAuth-Parametern.

Passwortprüfung, zeitlich begrenzte Herausforderungen und Fehlversuche werden in
PostgreSQL geführt. Fünf Fehlversuche pro Konto sperren weitere Versuche für das
laufende Fünfminutenfenster; zusätzlich gilt eine IP-Grenze. Ein Passwort allein
erzeugt kein Sitzungstoken. TOTP folgt RFC 6238, zulässige Uhrabweichung ein Schritt.
Bereits benutzte Schritte und Herausforderungen werden nicht erneut akzeptiert.
Rollen-/Passwortwechsel oder Kontosperrung machen eine begonnene Anmeldung ungültig.

Authenticator-Schlüssel liegen verschlüsselt in PostgreSQL; der Fernet-Schlüssel
bleibt in `/var/lib/smartplan-online/vault.key`, Modus 0400, unter dem Dienstkonto.
Wiederherstellungscodes und Sitzungen werden als Hash gespeichert. Das Datenverzeichnis
ist 0700. Der Fernet-Schlüssel muss für eine Wiederherstellung separat und geschützt
verfügbar sein; ein reiner Datenbank-Dump enthält ihn nicht.

## Sicherung und Wiederherstellung

Ein täglicher systemd-Timer erstellt konsistente `pg_dump`-Archive samt SHA-256
unter `/var/lib/smartplan-online/backups` (0600). Es gibt keine automatische
Löschung alter Sicherungen und noch keine automatische Fehlerbenachrichtigung.
Speicherverbrauch und Journal kontrollieren. Manueller Lauf:

```bash
systemctl start smartplan-online-backup.service
```

Zum Wiederherstellen zunächst als PostgreSQL-Administrator eine **neue** Datenbank
mit dem Online-Dienstkonto als Besitzer erstellen. Das Werkzeug
`python -m online.restore DATEI.dump NEUER_DATENBANKNAME` wird unter diesem
Dienstkonto mit den vorhandenen Dienst-Umgebungsvariablen ausgeführt. Es prüft
SHA-256, leeres und anderes Ziel, Schema und PDF-Bytes. Sitzungen und offene
Anmeldungen werden in der Kopie gelöscht. Die Kopie wird nicht automatisch aktiviert.

Die lokalen Dumps und vorhandenen Hetzner-Backups ersetzen kein getrenntes
verschlüsseltes Sicherungsziel. Dieses, die geschützte Sicherung des Vault-Schlüssels,
Aufbewahrung, Überwachung und Zuständigkeit bleiben vor echten Kundendaten festzulegen.

## Diagnose und Rücknahme

```bash
systemctl status smartplan-online --no-pager --full
journalctl -u smartplan-online -n 40 --no-pager
systemctl list-timers smartplan-online-backup.timer --no-pager
```

`/ready` prüft tatsächlichen Datenbankzugriff und liefert bei Störung 503.
Nach einem Verbindungsverlust wird bei der nächsten Anfrage neu verbunden;
ein abgebrochener Schreibvorgang wird nicht automatisch wiederholt.

Bei Verlust von Authenticator und sämtlichen Wiederherstellungscodes kann ein
Administrator über den bestehenden SSH-Zugang gezielt
`manage-online.sh reset-mfa EMAIL` ausführen. Das löscht MFA und Sitzungen dieses
Kontos und verlangt beim nächsten Login eine neue Einrichtung.

Für die Rücknahme nach erfolgreicher Aktivierung die gesicherte ursprüngliche
Caddy-Datei aus `/etc/smartplan-online/Caddyfile.before` wieder nach
`/etc/smartplan-https/Caddyfile` installieren und `smartplan-https` neu laden.
Anschließend nur Online-Dienst und dessen Backup-Timer deaktivieren. Datenbank,
Schlüssel, Sicherungen und der bisherige SQLite-Pilot bleiben bestehen.

Updates sind keine erneute Erstinstallation. Dafür werden vorab Sicherung,
geprüfte Migration und Austausch der separaten Codekopie mit anschließendem
Neustart und Abnahme vorbereitet.

## Automatisierte Nachweise und verbleibende Arbeiten

19 PostgreSQL-/Anmeldefälle prüfen unter anderem bestehende Domänenregeln,
Code-Wiederverwendung, Limits über Prozessgrenzen, Rechteentzug, paralleles
Unterzeichnen, Verbindungsverlust sowie echten Dump/Restore mit byteidentischem PDF.
Ein zusätzlicher Test startet Caddy mit explizit vertrauter Test-CA, die echten
Gunicorn-Parameter aus der Unit, zwei Worker und PostgreSQL; MFA, PDF und
API-Neustart werden durch die verschlüsselte Verbindung geprüft. Diese lokalen
Tests sind kein Nachweis des systemd-Starts auf der Nutzer-VM.

Noch separat: geprüfte Übernahme einer SQLite-Sicherung mit echten Daten,
OneDrive-Verbindung, echte iPhone-Signierung/Verteilung, Last-/Betriebsabnahme,
getrennte verschlüsselte Backups und Betreuung. Die bestehende lokale Nutzung
bleibt bis zur erfolgreichen späteren Datenübernahme verfügbar.
