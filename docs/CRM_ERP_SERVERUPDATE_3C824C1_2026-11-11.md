# Vorbereitetes Serverupdate für den Auslagenstand 3c824c1

Der Quellstand `3c824c174ec6247d50219a70612ba42fed75d017` ergänzt die
[unternehmensweite Auslagenoriginalsperre](CRM_ERP_AUSLAGEN_ORIGINALSPERRE_2026-11-11.md).
80 betroffene Backend-/Reisefälle, drei wirkliche PostgreSQL-/MFA-/Konkurrenz-/
Komplettrestorefälle, zwölf native Personalprüfungen, gesamte Appanalyse,
1.120 Browsermodulfälle und der tatsächliche Browserablauf bestehen.
Der gemeinsame [Developmentnachlauf](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42966124379)
läuft noch. Diese Anleitung ist bis zu dessen erfolgreichem Abschluss nur
vorbereitet. Pakete und tatsächliche Auslieferung stehen im
[Lieferstand](CRM_ERP_LIEFERSTAND_AKTUELL.md).

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
  smartplan_backup_ref="backup/server-before-3c824c1-$(date -u +%Y%m%dT%H%M%SZ)"
  git branch "$smartplan_backup_ref" "$smartplan_previous_commit"
  git fetch origin codex/testupdate-0.7-projects-20261104
  git switch --detach 3c824c174ec6247d50219a70612ba42fed75d017
  test "$(git rev-parse HEAD)" = 3c824c174ec6247d50219a70612ba42fed75d017
  git config --local tar.umask 0022
  bash deploy/hetzner/online/update-online.sh
  systemctl is-active smartplan-online.service smartplan-https.service smartplan-plan-import.service
  test "$(cat /opt/smartplan-online/SOURCE_COMMIT)" = 3c824c174ec6247d50219a70612ba42fed75d017
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
Quellstand gehörigen Windows-/iPhone-Pakete verwenden. Die Freigaberücknahme
benötigt Personalprüfrechte und eine andere Person als Mitarbeiter/Einreicher.
Sie erscheint nur bei der neuen Fähigkeit `personnel_expense_originals_v2`. Frühere Profile und
Lohnoriginale bleiben erhalten; vorhandene echte Abrechnungen nicht als
synthetische Testdaten verwenden.

Die [34 Gerätefälle](CRM_ERP_KUNDENTEST_PROTOKOLL_0_13.csv) bleiben bis zur
wirklichen Durchführung ungeprüft. Signiertes Paket, TestFlight-Verteilung,
Installation und Fach-/Sicherheitsabnahme sind getrennte Nachweise.
