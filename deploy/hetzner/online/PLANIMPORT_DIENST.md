# Geschützter Planimportdienst

Der Importcontroller liest vollständige Projektquellen aus PostgreSQL. Jeder
Parser startet in einer eigenen Bubblewrap-Umgebung mit privaten Netzwerk-,
Prozess- und Mount-Namespaces. Er sieht Systembibliotheken, seine festgehaltene
Python-Runtime und den Importcode nur lesbar. Das Original wird als einzelne
Datei ebenfalls nur lesbar eingebunden. Datenbank, Hostprozesse, Home-Verzeichnisse,
Vault, Dienstkonfiguration und geerbte Zugangsdaten sind dort nicht verfügbar.

Die Erkennung arbeitet auf privaten tmpfs-Dateisystemen: 128 MiB für temporäre
Dateien und 96 MiB für Ergebnisse. Nur zwei vorab angelegte Hostdateien können
beschrieben werden; die Dateigrößenbegrenzung und anschließende Schema-/Hash-
Prüfung gelten zusätzlich. Es gibt keinen beschreibbaren Host-Ausgabeordner.
Ein Parserabsturz beendet das betroffene Dokument; ein fehlgeschlagener
Sandboxstart verbraucht seinen Versuch nicht und beendet den Dienst mit Fehler.
Das Original bleibt in beiden Fällen erhalten.

Die systemd-Unit begrenzt den gesamten Controller samt Parser auf 1536 MiB,
64 Tasks und 150 Prozent einer CPU. Beim Stoppen wird die ganze Prozessgruppe
der Unit beendet. Der Controller benötigt für lokales PostgreSQL `AF_UNIX` und
für Bubblewrap `AF_NETLINK`; Internet-Socketfamilien sind nicht freigegeben.
`ProtectKernelTunables` bleibt bewusst aus, da dessen gesperrte Proc-Unterbäume
den unprivilegierten Aufbau des neuen Proc-Mounts verhindern. Im Parser sind
Root-, Proc-, Geräte-, Code-, Runtime- und Quellen-Mounts schreibgeschützt.

## Voraussetzung und Vorbereitung

Diese Anleitung beschreibt einen vorbereiteten Entwicklungsstand, keine bereits
erfolgte Bereitstellung auf dem Nutzer-Server. Vor echten Plänen sind die
automatisierten Prüfungen und die synthetische Abnahme auf dem tatsächlichen
ARM64-Server abzuschließen. Handschrift, Raum-/Wandinterpretation, Perspektive,
Maßstab sowie DXF/DWG sind damit nicht fachlich abgenommen.

Ziel ist der vorhandene Ubuntu-24.04-Server mit systemd, lokaler PostgreSQL-
Peer-Anmeldung und dem Dienstkonto `smartplan-online`. Zuerst muss der
[geprüfte API-Updateablauf](UPDATE_0_7.md) mit genau dem auf GitHub geprüften
Quellcommit abgeschlossen sein. Er bereitet Schema 3 in einer separaten
Datenbank vor und behält die bisherigen Originale und Sicherungen.
Der neue Worker ist optional und wird durch dieses API-Update nicht erstmals
installiert oder gestartet.

Im SSH-Serverfenster als root, aus dem sauberen, geprüften Checkout:

```bash
cd /opt/smartplan-test
bash deploy/hetzner/online/install-plan-import.sh
```

Der Installer verlangt denselben bereits installierten Quellcommit. Er nutzt
die gemeinsame Updatesperre und verweigert einen offenen Updatevorgang oder
eine vorhandene Importunit/Runtime. Er installiert Bubblewrap, lokale deutsche
und englische Tesseract-Sprachdaten sowie eine eigene Parser-Venv. Die
Namespaces, Pakete und Sprachen werden als tatsächlicher Dienstbenutzer mit
`NoNewPrivileges` vor Datenbankzugriff geprüft. Fehlende Isolation führt zum
Abbruch; es gibt keinen automatischen Entwicklungsmodus.

Der Installer bereitet die Unit nur vor. Er startet oder aktiviert sie nicht.
Bei Fehlern entfernt er ausschließlich seine neu angelegten Runtime-/Unitdateien;
gemeinsam genutzte Systempakete und vorhandene App-/Daten-/Konfigurationsdateien
bleiben erhalten. Bestehende Installationen werden nicht überschrieben.

## Synthetische Abnahme auf dem eigenen Server

Der reguläre Worker bleibt zunächst inaktiv und darf noch nicht für den
automatischen Start aktiviert sein. Die folgende Abnahme erstellt eine
neue, leere Datenbank mit zufälligem Namen und eine eigene temporäre Unit. Ihre
einzige Abweichung von der geprüften regulären Unit ist eine separate
EnvironmentFile mit genau dieser Testdatenbank. Die aktive App-Konfiguration
und ihre eventuell wartenden echten Planquellen werden nicht verändert oder
verarbeitet.

```bash
cd /opt/smartplan-test
bash deploy/hetzner/online/accept-plan-import.sh
```

Der Ablauf verarbeitet ausschließlich generierte Pläne, prüft Original-/PNG-/
JSON-Hashes und Erkennungsstatus, stoppt einen tatsächlich laufenden Parser samt
Nachkommen und verarbeitet den wieder freigegebenen Auftrag nach Neustart.
Seine eigene Unit, Testdatenbank und temporären Dateien werden anschließend
entfernt. Ein fehlgeschlagener Stopp behält ausschließlich diese Testobjekte zur
Prüfung; es werden keine fremden Prozesse oder Datenbankclients beendet.

Bleibt ein Doctor-/Namespacefehler, sind Kernel-/AppArmor-Regeln, Bubblewrap und
die exakt festgehaltenen Runtimepakete zu prüfen. Nicht auf
`--unsandboxed-development` ausweichen und keine globalen Schutzregeln abschalten.
Der eigene Entwicklungsmodus ist nur für synthetische lokale Tests vorgesehen.

## Regulärer Betrieb nach Abnahme

Erst nach geprüfter Serverabnahme den Dienst gezielt starten und aktivieren:

```bash
systemctl enable --now smartplan-plan-import.service
systemctl status smartplan-plan-import.service --no-pager
journalctl -u smartplan-plan-import.service -n 30 --no-pager
```

Der Start wiederholt den Doctor, bevor ein Auftrag beansprucht wird. Danach
verarbeitet der Worker vollständige Uploads, auch wenn das ursprüngliche Handy
nicht mehr verbunden ist. Eine geschlossene iOS-App garantiert weiterhin keine
sofortige Hintergrundübertragung; lokal bestätigte Originale bleiben erhalten.

Für spätere API-Updates wird eine vorhandene bekannte Unit stets vor dem
Datenbankklon gestoppt. Nur ein zuvor aktiver Worker wird nach der bestätigten
Aktivierungsgrenze wieder aufgenommen. Unbekannte Units, Drop-ins, DSN-Overrides
oder unsichere Stoppeinstellungen führen zum Abbruch. Änderungen an Runtime-
Locks oder Unitdatei benötigen einen gesondert geprüften Aktualisierungsablauf;
der Erstinstaller überschreibt sie nicht. Der Doctor verweigert veraltete Pakete.
