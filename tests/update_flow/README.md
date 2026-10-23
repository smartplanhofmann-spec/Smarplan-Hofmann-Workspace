# Prüfung der Server-Update- und Importvorbereitung

Aus dem Repository:

```bash
bash scripts/test-update-flow.sh
```

Der Runner verwendet einen kurzlebigen Docker-Container (`python:3.12-slim`),
mountet das Repository ausschließlich lesend und sperrt das Containernetzwerk.
Die Produktionspfade entstehen nur im Dateisystem dieses Containers. Der Test
verweigert einen direkten Start außerhalb dieser ausdrücklich markierten
Testumgebung.

Geprüft werden die tatsächlichen `deploy/hetzner/online/update-online.sh` und
`deploy/hetzner/online/install-plan-import.sh`:
Bash-Bedingungen, Fehlerbehandlung und `EXIT`-Trap laufen unverändert, ebenso
`install`, `mv`, `ln`, `flock`, `stat` und die echten JSON-Readiness-Assertions.
Systemdienste, Git-Archiv, Python-Venv/Helper und PostgreSQL-Kommandos werden durch
klar abgegrenzte synthetische Antworten ersetzt. Die Datenbankvorbereitung selbst
ist separat mit echten PostgreSQL-Dumps in `backend/online/test_release.py`
geprüft. Dies ist weder eine systemd- noch eine native Serverabnahme.

Die Fälle prüfen Erfolg, Neustart des HTTPS-Proxys vor dem API-Stopp,
Readiness-Abbruch vor öffentlicher Freigabe, Wiederherstellung physischer und
verlinkter Erstinstallationen, fehlgeschlagene Verzeichnis-/Linkwechsel,
nicht bestätigten Dienststopp, abweichende Units/Drop-ins/Umgebungsüberschreibungen,
fehlende Wartungssperre, Platzmangel vor der
Wartung, vorhandene/unbekannte Journale sowie den ursprünglichen Timerzustand.
Ein nach öffentlicher Freigabe angenommener Schreibvorgang wird bei anschließendem
Fehler ausdrücklich auf Erhaltung geprüft; ein erneuter automatischer Updateversuch
muss dann am vorhandenen Journal scheitern.

Eine vorhandene Importworker-Unit wird unabhängig vom zuvor gemeldeten Aktivzustand
vor der Datenbankprüfung gestoppt; auch ein ausstehender Neustart und ein später
gestarteter Worker werden simuliert. Nur ein vorher aktiver Worker wird danach
wieder gestartet. Die Fälle prüfen außerdem die bekannte Unit, ihre wirksame
Umgebungsdatei und begrenzte cgroup-Beendigungseinstellungen, einen nicht bestätigten
Stopp, SIGTERM direkt nach dem Worker-Stopp sowie die Erhaltung eines Worker-
Schreibvorgangs nach der Aktivierungsgrenze. Eine Installation ohne Worker bleibt
unterstützt. Die Stubs beweisen die Reihenfolge und Fehlerbehandlung; die tatsächliche
Beendigung von Parser-/OCR-Nachkommen braucht gesonderte Prozess- und systemd-Tests.

Die separate Installer-Testklasse prüft Vorbereitung ohne Start oder Aktivierung
des Workers, den gemeinsamen Verwaltungslock und Updatejournal-Guard, passenden
API-Quellstand, vorhandene Runtime-/Unit-/Aktivierungspfade sowie Bereinigung bei
Paket-, Venv-, Doctor- und Unitkopiefehlern. Echte SIGTERM-Signale treffen auch die
Grenze direkt nach Verzeichnis-/Dateierzeugung. Bereits vorhandene oder später
fremd angelegte Dateien und gemeinsame Systempakete bleiben erhalten. Die
vorhandenen Updatefälle werden durch die gemeinsame Fixture nicht doppelt geerbt.

Nur im kurzlebigen Container wird die unterstützte Ubuntu-Kennung simuliert.
`runuser` und `setpriv` bleiben echt; der simulierte Doctor muss unter UID/GID 2001
mit `NoNewPrivs=1` und ohne geerbte Zugangsdaten laufen. Der Inline-Preflight nutzt
die echten `read_environment`-/`validate_dsns`-Funktionen; libpq-Verbindungsstrings
werden an der Adaptergrenze synthetisch zerlegt. Jeder Datenbank-, Migrations-
oder Claimzugriff scheitert ausdrücklich. Apt, Pythonpakete, Doctor-Erkennung und
systemd bleiben simuliert; diese Fälle belegen keine Installation oder
Erkennungsabnahme auf einem echten Server.

Die Stubs enthalten nur fiktive Daten. Sie öffnen keine realen Dienstverbindungen
und lesen keine Zugangsdaten des Hostsystems.
