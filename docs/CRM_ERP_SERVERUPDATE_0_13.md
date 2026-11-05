# Vorbereitete Serverumstellung auf 0.13.0

Der Nutzer hat den sauberen Servercheckout a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5
per Screenshot bestätigt. Zuletzt installierter Stand war
6371da1ec3641818b158ce3d3e132be674bc397e; beide Dienste aktiv, Datenbank ok,
Schema 7, Businessmodus und rund 33 GB freier Speicher. Direkter Cloudzugriff
ist nicht konfiguriert. Eine tatsächliche Umstellung wurde noch nicht bestätigt.

Der feste Zielcommit entspricht dem tatsächlichen Windows-/iPhone-Prüfbuild.
Server, Update/Recovery, Windows, iOS-Simulator und Backend bestehen dort.
Die beiden folgenden Browser-/App-Fixturekorrekturen betreffen ausschließlich
Tests; alle Produktquellen sind bytegleich zum Ziel. Der Browser-Gesamtjob
ist auf e7089a6 ebenfalls erfolgreich. Dessen einzelne App-Zeitabweichung ist
als bestehender vollständiger HTTP-Fall reproduziert und mit ganzsekündiger
Testuhr an drei Zeitpunkten sowie bei aktueller Uhrzeit nachgeprüft. Die
produktive Subsekunden-Rundung bleibt unverändert; die Grenze ist in
[einem eigenen Nachweis](evidence/project-time-clock-2026-11-05/verification.json)
benannt. Kein neuer vollständig grüner Remote-Gesamtlauf wird behauptet.

## Ausführung im bestehenden SSH-Fenster

**Dieser Block startet die Serverumstellung mit einem Wartungsfenster.**
Er verankert zunächst die acht bislang nicht lokal verzweigten Altcommits mit
einem Sicherungsbranch. Der geprüfte bestehende Updateablauf erstellt ein
Release, eine Sicherung und eine getrennte Kandidatendatenbank. Unbekannte
Konfigurationen werden vor der Umschaltung abgewiesen. Das SSH-Fenster bis
zum Abschluss geöffnet lassen.

```bash
cd /opt/smartplan-test &&
test "$(git rev-parse HEAD)" = a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5 &&
git branch backup/server-before-0.13-20261105 6371da1ec3641818b158ce3d3e132be674bc397e &&
bash deploy/hetzner/online/update-online.sh &&
systemctl is-active smartplan-online.service smartplan-https.service &&
cat /opt/smartplan-online/SOURCE_COMMIT &&
curl --fail --silent --show-error --max-time 15 https://office.smartplan-hofmann.de/ready
```

Der Branch wird ohne Force angelegt. Existiert er bereits, stoppt der Block;
dann seinen vorhandenen Zielcommit prüfen, statt ihn zu überschreiben.
Erwartetes erfolgreiches Ende: Testupdate aktiviert: a93cb4d..., beide Dienste
active, installierter Quellstand exakt a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5
und /ready mit Datenbank ok. Die Kompatibilitätskennung darf weiterhin
0.12.0-online-pilot heißen; sie ist keine App-Buildnummer.

Bei einem Abbruch die letzten Ausgabezeilen und den genannten Journalpfad
prüfen. UPDATE_IN_PROGRESS nicht blind entfernen und den Ablauf nicht blind
wiederholen. Vor öffentlicher Aktivierung versucht der Ablauf die geprüfte
Rückkehr; nach öffentlicher Aktivierung werden neue Schreibvorgänge erhalten
und es erfolgt kein automatischer Rücksprung auf einen alten Datenbestand.
Originaldatenbank, vorherige Releases und Sicherungen bleiben erhalten.

Nach bestätigter Umstellung folgen Browser-/Windows-Anmeldung und die
vorbereiteten tatsächlichen Gerätefälle. Installierbare signierte iPhone-
Verteilung und TestFlight bleiben eigenständig offen; Löhne und Buchhaltung
bleiben zurückgestellt.
