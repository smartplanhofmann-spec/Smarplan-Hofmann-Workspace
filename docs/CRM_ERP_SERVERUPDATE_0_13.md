# Aktueller Stand: Parser repariert, kontrollierter Updateabschluss vorbereitet

Der Nutzer bestätigt um 20:23 UTC den bestandenen Sandbox-Starttest, den
anschließend laufenden Importcontroller, drei aktive Dienste und Datenbank ok.
Die roten Startfehler von 18:35 in demselben Ausschnitt sind historisch.
Der [kontrollierte Abschlusshelfer](CRM_ERP_SERVERUPDATE_ABSCHLUSS_0_13.md)
prüft jetzt tatsächliche Code-/Prozess-/Datenbankbindung und Timer, bevor er
das noch offene Update abschließt. Seine Serverausführung ist noch nicht
bestätigt. Die neue Datenbank, Releases und Sicherungen bleiben erhalten.
Die nachfolgenden Update-/Reparaturblöcke sind Verlauf, keine neue Startanweisung.

## Verlauf vor der erfolgreichen Parserreparatur

# Vorheriger nächster Schritt: Parserreparatur mit automatisch ermitteltem Journal

Der zuletzt verwendete ausgeschriebene Journalpfad war falsch transkribiert.
Der Phasentest hat die Paket-/Dienständerungen vorher abgebrochen. Die
[aktualisierte Parserreparatur](CRM_ERP_PLANIMPORT_REPARATUR_0_13.md) ermittelt
den korrekten Journalpfad jetzt aus dem tatsächlich aktiven App-Release.
Der neue Serverstand und die Datenbank bleiben erhalten. Keine der darunter
archivierten API-Updatefolgen erneut starten und das offene Journal nicht löschen.

## Verlauf

# Aktueller Befund: Parser-Pillow passt nicht zum aktivierten Quellstand

Installierter A93-Commit und API-/Datenbankbereitschaft sind inzwischen vom
Nutzer bestätigt. Der Parser besitzt Pillow 12.3.0 statt benötigter 13.0.0;
die anderen drei gesperrten Parserpakete stimmen überein. Die konkrete
[gesicherte Parser-Reparatur](CRM_ERP_PLANIMPORT_REPARATUR_0_13.md) ist vorbereitet.
Die normale Sandboxprüfung bleibt aktiv. Der Vorgang ist noch nicht als
erfolgreich abgeschlossen bestätigt; Journal und neue Datenbank bleiben bestehen.

## Verlauf und bisherige Updatebefehle

# Aktueller Stand: Aktivierungsgrenze überschritten, Planimport gestört

Der Nutzer bestätigt nach dem erneuten Versuch den Abbruch **nach** der
Aktivierungsgrenze. Neuer Code und neue Datenbank bleiben erhalten; der
Planimport-Dienst scheitert beim Start. Journal:
`/etc/smartplan-online/updates/a93cb4d02eab-20261105T183445-10529`.
[Beobachtete Ausgabe](evidence/project-update-forward-2026-11-05/observed-activation-failure.json).

**Die folgenden früheren Updateblöcke sind jetzt Verlauf und dürfen nicht
noch einmal gestartet werden. Kein Rücksprung auf die alte Datenbank und
UPDATE_IN_PROGRESS nicht löschen.** Zuerst API/HTTPS-Status, installierten
Quellstand, Bereitschaft und das Journal des fehlgeschlagenen Importdienstes
lesen. Ursache des Workerfehlers und aktueller API-Zustand sind noch nicht
über Diagnoseausgaben bestätigt. Keine Sandbox- oder Rechteprüfung umgehen.
Nach der Reparatur sind die beabsichtigten Dienste/Timer und der neue
Datenbank-/Codebezug zu prüfen, bevor das Update kontrolliert abgeschlossen wird.

## Verlauf vor dieser Aktivierung

# Aktueller Stand nach dem Berechtigungsabbruch

Das erste Update auf a93cb4d wurde am 05.11.2026 bei der Release-Rechteprüfung
abgebrochen. Der Nutzer bestätigt danach zwei aktive Dienste und den weiterhin
installierten Stand 6371da1e. Das neue Release enthielt root-eigene 0775-
Verzeichnisse und 0664-Dateien. [Tatsächlicher Fehler und Nachprüfung](evidence/project-update-permissions-2026-11-05/verification.json).
Git archive erzeugte diese Rechte mit seiner Standardmaske 0002; root-tar
übernahm sie trotz Shell-umask 0022. Der Guard arbeitet korrekt und bleibt aktiv.
Die unten archivierte erste Befehlsfolge nicht unverändert erneut ausführen:
ihr Sicherungsbranch wurde vor Beginn des ersten Versuchs bereits angelegt.

## Vorbereiteter erneuter Versuch

**Der folgende Block startet erneut die koordinierte Serverumstellung.**
Er prüft den festen Zielcommit und den vorhandenen Sicherungsbranch. Die
repository-lokale Archivmaske wird auf 0022 eingeschränkt; das ist für den
bereits gebauten und ausgecheckten A93-Stand ausreichend und mit echtem Git
sowie GNU tar als root geprüft. Der dauerhafte Quellfix erzwingt zusätzlich
umask-beachtende Extraktion in Update und Erstinstallation. Kein pauschales
chmod und keine Änderung der Schutzprüfung sind nötig. Vorhandene Journale
oder fehlgeschlagene Releases werden nicht manuell entfernt.

```bash
cd /opt/smartplan-test &&
test "$(git rev-parse HEAD)" = a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5 &&
test "$(git rev-parse backup/server-before-0.13-20261105)" = 6371da1ec3641818b158ce3d3e132be674bc397e &&
git config --local tar.umask 0022 &&
bash deploy/hetzner/online/update-online.sh &&
systemctl is-active smartplan-online.service smartplan-https.service &&
cat /opt/smartplan-online/SOURCE_COMMIT &&
curl --fail --silent --show-error --max-time 15 https://office.smartplan-hofmann.de/ready
```

Das SSH-Fenster geöffnet lassen. Anschließend werden Testupdate aktiviert:
a93cb4d..., zwei active-Zeilen, der volle installierte Zielcommit und /ready
mit Datenbank ok erwartet. Die Backend-Kompatibilitätskennung darf weiterhin
0.12.0-online-pilot lauten. Bei einem erneuten Abbruch die letzten Ausgabezeilen
prüfen; nicht blind Journale löschen oder auf eine alte Datenbank wechseln.
Eine erfolgreiche tatsächliche Serverumstellung ist erst mit deren Ausgabe
bestätigt und wird hier noch nicht behauptet.

## Ursprüngliche Vorbereitung und erster Versuch

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
