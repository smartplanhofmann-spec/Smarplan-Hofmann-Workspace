# Prüfung des Server-Updateablaufs

Aus dem Repository:

```bash
bash scripts/test-update-flow.sh
```

Der Runner verwendet einen kurzlebigen Docker-Container (`python:3.12-slim`),
mountet das Repository ausschließlich lesend und sperrt das Containernetzwerk.
Die Produktionspfade entstehen nur im Dateisystem dieses Containers. Der Test
verweigert einen direkten Start außerhalb dieser ausdrücklich markierten
Testumgebung.

Geprüft wird das tatsächliche `deploy/hetzner/online/update-online.sh`:
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

Die Stubs enthalten nur fiktive Daten. Sie öffnen keine realen Dienstverbindungen
und lesen keine Zugangsdaten des Hostsystems.
