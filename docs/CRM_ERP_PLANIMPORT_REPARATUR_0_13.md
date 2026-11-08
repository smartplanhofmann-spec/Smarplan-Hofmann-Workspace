# Reparatur inzwischen auf dem Server bestätigt

Der Nutzer bestätigt am 05.11.2026 um 20:23 UTC die bestandene Sandboxprüfung,
anschließend mehrfach idle im aktuellen Importcontroller, drei aktive Dienste
und API-/Datenbankbereitschaft ok. [Erfasster Befund](evidence/project-update-forward-2026-11-05/observed-parser-repair-success.json).
Den nachstehenden Reparaturblock nicht erneut ausführen. Der separate
[Updateabschluss](CRM_ERP_SERVERUPDATE_ABSCHLUSS_0_13.md) ist inzwischen
ebenfalls durch die tatsächliche SSH-Ausgabe bestätigt: drei Dienste und
Sicherungstimer aktiv, aktuelle Sandbox-/Datenbankbindung geprüft und
Aktivierungsmarker entfernt. Die Datenbank wurde nicht zurückgeschaltet.

# Korrektur des Journalpfads im früheren Reparaturblock

Der zuvor ausgeschriebene Zeitstempel im Journalpfad war eine fehlerhafte
Transkription aus dem Screenshot. Der Nutzer bestätigt, dass der zusätzliche
Phasentest deshalb vor dem Importdienst-Stopp, einer Sicherung oder einer
Paketänderung abgebrochen ist. Die folgende Fassung leitet den Journalnamen
über readlink vom tatsächlichen aktiven App-Release ab und prüft dessen
Struktur und Metadatendatei. Keine Auswahl anhand des neuesten Verzeichnisses.

# Planimport nach aktivierter A93-Serverumstellung

Der Nutzer bestätigt jetzt den installierten A93-Commit und /ready mit
Datenbank ok. Der vorhandene Parser-Starttest verweigert die ältere separate
Parser-Venv: Pillow 12.3.0 statt der im aktiven Quellstand verlangten 13.0.0.
NumPy 2.3.5, OpenCV 4.13.0.92 und pypdfium2 5.14.0 stimmen überein.
[Erfasste Versionsdaten](evidence/project-update-forward-2026-11-05/confirmed-parser-package-mismatch.json).
Das ist eine bestätigte Startblockade; weitere Fehler sind dadurch noch
nicht ausgeschlossen. Die Sandbox wird nicht abgeschaltet.

## Vorbereitete manuelle Reparatur im bestehenden SSH-Fenster

Der Block erwirbt die gemeinsame Verwaltungssperre, prüft installierten
Zielcommit und Aktivierungsphase, stoppt nur den Importdienst und sichert
seine Venv einschließlich innerer Symlinks in einem neuen privaten Ordner.
Der Sicherungspfad wird im bestehenden privaten Updatejournal angehängt.
Nur Pillow wird auf die verlangte Version gebracht; --no-deps verhindert
dabei zusätzliche Paketänderungen. Eine lesbare Dateimaske gilt für die neue
Paketinstallation. Die separate API-Venv und die Datenbank werden nicht
umgestellt. Der normale Dienststart führt die tatsächliche Sandboxprüfung
unter den bestehenden systemd-Grenzen aus und nimmt bei Erfolg die zuvor
aktive Importwarteschlange wieder auf. Danach sind Zustand und Logs zu prüfen.

```bash
(
  set -e
  umask 0077
  exec 9>/run/lock/smartplan-online-update.lock
  flock -n 9
  test "$(cat /opt/smartplan-online/SOURCE_COMMIT)" = a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5
  test "$(cat /etc/smartplan-online/UPDATE_IN_PROGRESS)" = activating
  smartplan_active_app=$(readlink -e /opt/smartplan-online/app)
  test "$(basename "$smartplan_active_app")" = app
  smartplan_active_release=$(dirname "$smartplan_active_app")
  test "$(dirname "$smartplan_active_release")" = /opt/smartplan-online/releases
  smartplan_release_id=$(basename "$smartplan_active_release")
  smartplan_repair_journal="/etc/smartplan-online/updates/$smartplan_release_id"
  test -f "$smartplan_repair_journal/metadata.json"
  printf 'Aktives Updatejournal: %s\n' "$smartplan_repair_journal"
  test "$(cat "$smartplan_repair_journal/phase")" = activating
  test -f /opt/smartplan-plan-import/venv/pyvenv.cfg
  systemctl stop smartplan-plan-import.service
  smartplan_parser_backup=$(mktemp -d /opt/smartplan-plan-import/venv-before-pillow13.XXXXXX)
  cp -a -- /opt/smartplan-plan-import/venv/. "$smartplan_parser_backup/"
  chmod 0700 "$smartplan_parser_backup"
  printf '%s\n' "$smartplan_parser_backup" >> "$smartplan_repair_journal/parser-venv-backups.log"
  printf 'Parser-Sicherung: %s\n' "$smartplan_parser_backup"
  umask 0022
  /opt/smartplan-plan-import/venv/bin/python -m pip --disable-pip-version-check install --only-binary=:all: --no-deps pillow==13.0.0
  /opt/smartplan-plan-import/venv/bin/python -m pip check
  systemctl reset-failed smartplan-plan-import.service
  systemctl start smartplan-plan-import.service || {
    journalctl -u smartplan-plan-import.service -n 30 --no-pager -o short-iso
    exit 1
  }
  sleep 5
  journalctl -u smartplan-plan-import.service -n 20 --no-pager -o short-iso
  systemctl is-active smartplan-online.service smartplan-https.service smartplan-plan-import.service
  curl --fail --silent --show-error --max-time 15 https://office.smartplan-hofmann.de/ready
)

```

Der Shellblock war zunächst Vorbereitung. Die nachfolgende Nutzerausgabe
bestätigt inzwischen bestandene Sandbox-Vorprüfung, laufenden Controller und
drei aktive Dienste; siehe den aktuellen Befund am Dateianfang.
Der Cloud-Assistent hat den Server nicht direkt aufgerufen.
Das Updatejournal bleibt offen. Erst nach dem realen Dienst-/Bereitschafts-
und Datenbank-/Codeabgleich wird der Vorgang kontrolliert abgeschlossen.
Nicht die API-Aktualisierung wiederholen, keine alte Datenbank wiederherstellen
und UPDATE_IN_PROGRESS nicht blind entfernen.

## Vor künftigen Serverupdates

Der Incident zeigt, dass die getrennte Parser-Venv bei Änderung der
Quell-Abhängigkeiten mitgeführt oder vor der öffentlichen Aktivierungsgrenze
auf Kompatibilität geprüft werden muss. Diese Vorprüfung ist am 08.11.2026
im neuen Updatecode ergänzt: künftiger Backendcode, vorhandene Parser-Venv,
tatsächliche Dienst-UID und NoNewPrivileges, keine geerbten Zugangsdaten und
vollständiger bestätigter Sandboxbericht. Bei Fehlern beginnen weder Wartung
noch Dienststopp oder Kandidatendatenbank. Die Venv wird nicht automatisch
verändert. Die spätere tatsächliche systemd-Startprüfung bleibt bestehen.
[Arbeitsstand und aktueller Prüfnachweis](CRM_ERP_ARBEITSSTAND.md).
Die Installation dieses neuen Updatecodes auf dem realen Server ist separat
nachzuweisen; die damalige A93-Reparatur ist dadurch nicht rückwirkend geändert.
