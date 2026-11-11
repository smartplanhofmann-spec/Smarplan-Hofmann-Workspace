# Serverupdate für den geprüften RV-Stand ab6b615

Der Quellstand `ab6b61535a35f8306bbf04ebe6557acdb2ac3f41` besteht alle 20
eigenen [Developmentgruppen](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42923602362).
2.225 Backendfälle mit drei ausgewiesenen Auslassungen, Browser, PostgreSQL,
Windowsbau, Paketierung, Update und Restore sind erfolgreich. Der tatsächliche
Commitarchivlauf besteht zusätzlich 22 Fälle nach MFA. Die iPhone-Auslieferung
wird im [Lieferstand](CRM_ERP_LIEFERSTAND_AKTUELL.md) getrennt nachgewiesen.

Diese Anleitung ist konkret vorbereitet und syntaktisch geprüft. Sie wurde
aus dieser Cloud nicht am Server ausgeführt. Der letzte vom Nutzer bestätigte
Serverstand bleibt `a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5` vom 05.11.
Ein Quellcode-Push aktualisiert den installierten Server nicht automatisch.

## Zuerst die bekannte Verbindung öffnen

Auf dem vorhandenen Windows-PC in PowerShell:

```powershell
ssh -i "$env:USERPROFILE\.ssh\smartplan_hetzner" root@office.smartplan-hofmann.de
```

Der private Schlüssel bleibt auf dem eigenen PC. Sein Inhalt gehört nicht in
den Chat. Das nächste Befehlsfenster muss die verbundene Linux-SSH-Sitzung sein.

## Kontrolliertes Update auf den festen geprüften Commit

Der folgende Block erhält den bisherigen Quellcommit zusätzlich als lokalen
Sicherungsbranch. Das bestehende Updateverfahren erstellt und kontrolliert
die Datenbanksicherung und unterscheidet Abbruch vor beziehungsweise nach
Aktivierung. Keine Befehle zum manuellen Zurückschalten der Datenbank ergänzen.

```bash
(
  set -euo pipefail
  cd /opt/smartplan-test
  git diff --quiet
  git diff --cached --quiet
  smartplan_previous_commit=$(git rev-parse HEAD)
  smartplan_backup_ref="backup/server-before-ab6b615-$(date -u +%Y%m%dT%H%M%SZ)"
  git branch "$smartplan_backup_ref" "$smartplan_previous_commit"
  git fetch origin codex/testupdate-0.7-projects-20261104
  git switch --detach ab6b61535a35f8306bbf04ebe6557acdb2ac3f41
  test "$(git rev-parse HEAD)" = ab6b61535a35f8306bbf04ebe6557acdb2ac3f41
  git config --local tar.umask 0022
  bash deploy/hetzner/online/update-online.sh
  systemctl is-active smartplan-online.service smartplan-https.service smartplan-plan-import.service
  test "$(cat /opt/smartplan-online/SOURCE_COMMIT)" = ab6b61535a35f8306bbf04ebe6557acdb2ac3f41
  cat /opt/smartplan-online/SOURCE_COMMIT
  curl --fail --silent --show-error --max-time 20 https://office.smartplan-hofmann.de/ready
)
```

Bei lokalen Änderungen stoppt der Block vor dem Wechsel. Diese Änderungen
nicht durch Zurücksetzen oder erzwungenen Checkout beseitigen. Bei einer
Fehlermeldung den konkreten Befund und den erhaltenen Updatejournalpfad prüfen.
Nach Aktivierung können neue Schreibvorgänge bereits angenommen sein; ein
unkoordinierter Rückwechsel auf eine alte Datenbank wäre deshalb falsch.

## Nach dem tatsächlichen Update abgleichen

Erwartet werden drei aktive Dienste, genau der oben angegebene installierte
Quellcommit und ein erfolgreicher Bereitschaftsstatus. Dann im Browser neu
anmelden, die angezeigte installierte Quellkennung abgleichen und die zum
Quellstand gehörigen Windows-/iPhone-Pakete verwenden. Der private RV-Verlauf
benötigt die dafür vorgesehenen Personal- und Lohnrechte. Frühere Profile und
Lohnoriginale bleiben erhalten; vorhandene echte Abrechnungen nicht als
synthetische Testdaten verwenden.

Die [34 Gerätefälle](CRM_ERP_KUNDENTEST_PROTOKOLL_0_13.csv) bleiben bis zur
wirklichen Durchführung ungeprüft. Signiertes Paket, TestFlight-Verteilung,
Installation und Fach-/Sicherheitsabnahme sind getrennte Nachweise.
