# Serverupdate für den geprüften Quellstand 29b02c8

Diese Anleitung aktualisiert das vorhandene Testsystem mit dem kontrollierten
Updateverfahren. Der zugehörige tatsächliche Paket- und Prüfumfang steht im
[aktuellen Lieferstand](CRM_ERP_LIEFERSTAND_AKTUELL.md). Die Änderung des
Quellbranches aktualisiert den Server nicht automatisch.

## Verbindung vom vorhandenen Windows-PC

In PowerShell zuerst die bekannte Verbindung öffnen. Der private Schlüssel
bleibt auf dem eigenen PC; sein Inhalt gehört nicht in den Chat.

```powershell
ssh -i "$env:USERPROFILE\.ssh\smartplan_hetzner" root@office.smartplan-hofmann.de
```

## Kontrolliertes Update im verbundenen Serverterminal

Die folgenden Befehle gehören in die geöffnete Linux-SSH-Sitzung. Der feste
Commit ist der tatsächlich geprüfte Produktstand. Neuere reine
Dokumentationsnachträge werden nicht mit einem neuen Produktbau verwechselt.

```bash
(
  set -e
  cd /opt/smartplan-test
  git diff --quiet
  git diff --cached --quiet
  git fetch origin codex/testupdate-0.7-projects-20261104
  git switch --detach 29b02c82a12d4aa1dfc97eaa84638d840882612d
  test "$(git rev-parse HEAD)" = 29b02c82a12d4aa1dfc97eaa84638d840882612d
  git config --local tar.umask 0022
  bash deploy/hetzner/online/update-online.sh
  systemctl is-active smartplan-online.service smartplan-https.service smartplan-plan-import.service
  cat /opt/smartplan-online/SOURCE_COMMIT
  curl --fail --silent --show-error --max-time 20 https://office.smartplan-hofmann.de/ready
)
```

Vorhandene Änderungen nicht durch Zurücksetzen oder erzwungenen Checkout
beseitigen. Bei einer Fehlermeldung den konkreten Befund und den erhaltenen
Updatejournalpfad prüfen. Nach bereits erfolgter Aktivierung nicht von Hand
auf eine alte Datenbank zurückschalten: Zwischenzeitliche Schreibvorgänge
können bereits angenommen sein. Das bestehende Updateverfahren unterscheidet
diese Zustände ausdrücklich.

Erwartet werden drei aktive Dienste, der oben genannte installierte
Quellcommit und ein erfolgreicher Bereitschaftsstatus. Anschließend den
tatsächlich angezeigten installierten Stand im Browser abgleichen und die
passenden Windows-/iPhone-Clients gemäß ihrem eigenen Paketnachweis verwenden.

## Tatsächlicher Ausführungsstand

Die Anleitung ist vorbereitet, aber aus dieser Cloud nicht am Server
ausgeführt. Hier sind weder der dokumentierte SSH-Schlüssel noch ein
SSH-Agent eingerichtet. Der letzte vom Nutzer bestätigte Live-Stand bleibt
a93cb4d vom 05.11.; ein neuer Liveupdate wird nicht behauptet.
