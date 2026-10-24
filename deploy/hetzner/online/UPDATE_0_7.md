# Geschütztes Testupdate – separate Datenbank und geschlossene Freigabegrenze

**Aktueller Hinweis:** Der Dateiname stammt aus der früheren 0.7-Planung. Der
geschützte Ablauf wurde inzwischen beim bestätigten Nutzer-Update auf 0.8
(`c58b609`, Schema 3) eingesetzt. Der aktuelle vorbereitete Quellstand 0.9
verlangt **Schema 4**; dafür gilt zusätzlich
[das gebündelte Update 0.9](UPDATE_0_9.md). 0.9 ist noch nicht auf dem Nutzer-Server
bereitgestellt. Der folgende Text beschreibt den weiterhin verwendeten
Update- und Wiederanlaufmechanismus, keine erneute Erstinstallation.

Der neue Ablauf ist für die vorhandene Ubuntu-24.04-/PostgreSQL-16-Installation
mit Dienstkonto `smartplan-online`, lokalem Peer-Zugang und dem eigenen
Smartplan-Caddy-Dienst vorbereitet. Er wurde lokal mit echten Datenbankkopien
und in isolierten Tests des Shellablaufs geprüft. Der frühere
[Testupdateplan 0.7](../../../TESTUPDATE_0_7.md) dokumentiert die historische
Planung; die aktuellen Paket- und Abnahmeschritte stehen unter
[UPDATE_0_9.md](UPDATE_0_9.md).

## Vor dem Serverupdate

- Exakten Quell-Commit des grünen Testbranch-Builds festhalten. Die späteren
  Gerätepakete müssen diesen Quellstand beziehungsweise den daraus freigegebenen
  Release-Commit nennen. Der aktuelle Entwicklungsstand 0.9 erwartet Schema 4;
  das bestätigte laufende Schema 3 wird ausschließlich in der neuen
  Datenbankkopie migriert. Die bisherige Originaldatenbank bleibt erhalten.
- Den Wartungszeitpunkt abstimmen. Geöffnete Geräte behalten lokale Pläne und
  ausstehende Aufträge. Berichte und andere Online-Funktionen sind während der
  Wartung nicht erreichbar; noch laufende Vorgänge vorher abschließen.
- Vorhandene getrennte Betriebssicherung prüfen, insbesondere den dauerhaft
  benötigten Vault-Key und die geschützte Speicherkonfiguration. Der DB-Dump
  enthält nicht diese gesamten Dateikonfigurationen. Keine Schlüssel neu erzeugen
  oder in den Checkout beziehungsweise Chat kopieren.
- Platz für Originaldatenbank, neue vollständige Kopie, Dump und WAL sicherstellen.
  Das Skript prüft vor Wartungsbeginn eine konservative Mindestreserve: auf einem
  gemeinsamen Dateisystem mindestens dreimal die DB-Größe plus 512 MiB frei;
  bei getrennten Dateisystemen PostgreSQL zweimal DB-Größe plus 256 MiB und
  Backup DB-Größe plus 256 MiB. Andere Serverdienste können ebenfalls Platz
  verbrauchen; es werden keine alten Daten automatisch entfernt.
- Unveränderte API-/Backup-Unit und die bekannte Caddy-Konfiguration verwenden.
  Unbekannte systemd-Drop-ins oder direkte Umgebungsüberschreibungen werden
  vor der Wartung abgewiesen, statt eine falsche DB-Umschaltung zu riskieren.
- Ein bereits vorhandener Importdienst muss ebenfalls der geprüften Unit und
  Umgebung entsprechen. Er wird vor der Datenbankkopie stets vollständig
  gestoppt; nur ein zuvor aktiver Worker wird nach erfolgreicher Aktivierung
  wieder gestartet. Das Update installiert oder aktiviert keinen neuen Worker;
  dafür gilt der separate [Vorbereitungsablauf](PLANIMPORT_DIENST.md).
- Keine andere Verwaltung, Migration oder Speichereinrichtung parallel starten.
  Die gelieferten Helper verwenden denselben Lock und respektieren das
  unvollständige Updatejournal. Unerwartete weitere DB-Verbindungen führen zum
  Abbruch; das Skript beendet keine fremden Datenbankprozesse.

Im bestehenden SSH-Fenster als root den freigegebenen, vollständigen Quellstand
unter `/opt/smartplan-test` bereitstellen. Beispielsweise nach einem geprüften
Testlauf die konkrete SHA mit `git fetch origin` holen und ohne Force auf diesen
Stand wechseln; vorhandene lokale Änderungen zuerst klären. Kein ungeprüfter
Branch-Tip und keine uncommitteten Quelldateien werden installiert.
Dann:

```bash
cd /opt/smartplan-test
bash deploy/hetzner/online/update-online.sh
```

`install-online.sh` nicht erneut ausführen. Der Aufruf selbst ist der bewusste
Servereingriff; die GitHub-Builds und das Erstellen der Testpakete tun dies nicht.

## Tatsächlicher Ablauf

1. Neue Backend-Kopie und virtuelle Umgebung werden aus der exakten lokalen
   Commit-SHA in einem eigenen Releasepfad vorbereitet und geprüft.
2. Rootgeschütztes Updatejournal und unveränderte Sicherungskopien von Env,
   Caddy-Datei und `SOURCE_COMMIT` werden angelegt. `metadata.json` enthält
   Update-ID, neue/alte Codepfade und Datenbanknamen; keine Secretwerte.
3. Caddy erhält die bekannte Wartungskonfiguration. Der dedizierte HTTPS-Dienst
   wird neu gestartet, damit alte Proxy-Handler keine Requests bis zum neuen
   Backend offenhalten. Eine verifizierte lokale HTTPS-Anfrage muss 503 liefern.
4. Backup-Timer wird angehalten; ein laufender Dump darf fertig werden. Ein
   vorhandener Importworker wird samt Nachfahren gestoppt und sein inaktiver
   Zustand bestätigt. Danach wird der API-Dienst vollständig angehalten.
5. Erst jetzt entstehen der maßgebliche Dump und seine SHA-256-Datei. Eine neue
   DB `smartplan_online_u_...` wird als PostgreSQL-Administrator angelegt; die
   Dienstrolle restauriert und migriert ausschließlich diesen Kandidaten.
6. Die Wiederherstellung wird vor Migration über Fingerprints aller Zeilen aller
   Quelltabellen und der Sequenzen mit der Quelle verglichen. Nach Migration
   müssen bestehende Geschäftsdaten unverändert sein und alle gespeicherten
   PDFs ihren Hash bestätigen. Die aktive Original-DB bleibt unverändert.
7. Code-Verweise und nur die Datenbankzeile der Env werden atomar gewechselt.
   Eigentümer/Gruppe und Mode 0640 der Env bleiben erhalten. Der neue Dienst
   startet bei weiterhin gesperrtem öffentlichem API-Zugang. Loopback prüft
   Datenbank, Schema und Fähigkeiten der neuen Version.
8. **Vor** dem öffentlichen Reload wird `activating` mit Datei- und
   Verzeichnis-fsync gespeichert. Ab dieser Grenze schaltet kein Fehlerpfad
   automatisch auf die alte Datenbank zurück. Erst danach werden Requests
   freigegeben, der erwartete 401 ohne Anmeldung geprüft und der vorher aktive
   Sicherungstimer wieder gestartet.
9. Bei Erfolg steht die Phase auf `active`; die Pending-Sperre wird entfernt.
   Original-DB, alte Releases und Dump werden nicht gelöscht.

Rootjournal: `/etc/smartplan-online/updates/<Update-ID>/`

Dump und Arbeitsbericht: `/var/lib/smartplan-online/updates/<Update-ID>/`

Die Updatekopie erhält bestehende Sitzungen und Retry-Datensätze unverändert,
da sie denselben logischen Bestand ohne zwischenzeitliche Schreibzugriffe
fortführt. Die getrennte **Wiederherstellung einer Betriebssicherung** über
`online.restore` widerruft dagegen weiterhin normale und Offline-Sitzungen.

## Fehler und Wiederanlauf

**Vor `activating`:** Das Skript kann den bisherigen Code und die vorherige Env
wiederherstellen und mit der unveränderten Original-DB starten. Es restauriert
niemals einen Dump in die aktive DB. Erst nach bestätigtem alten Dienst wird die
Wartung geöffnet. Ein nicht bestätigter Dienststopp lässt die Wartung geschlossen;
die Konfiguration wird dann nicht weiter umgestellt. Kandidat und Backup bleiben
für die Diagnose erhalten.

**Ab `activating`:** Neuer Code und neue Datenbank bleiben erhalten. Auch ein
fehlgeschlagener Caddy-Reload oder eine fehlgeschlagene öffentliche Probe kann
bereits mit angenommenen neuen Schreibvorgängen zusammenfallen. Diese müssen
erhalten bleiben. Der Sicherungstimer wird bestmöglich für die neue DB gestartet;
Fehler werden ausdrücklich ausgegeben. Die weitere Behebung erfolgt vorwärts.

**Nach Prozess-/VM-Abbruch:** Jede vorhandene oder symbolische
`/etc/smartplan-online/UPDATE_IN_PROGRESS` blockiert einen neuen Updateaufruf und
andere Verwaltungshelper. Nicht löschen, um einfach erneut zu starten. Zuerst
`metadata.json`, `phase`, Dienstzustand, installierte Codeziele und aktive
DB-Auswahl am Server prüfen. Keine Env- oder Schlüsselwerte in Logs/Chat ausgeben.

Bei `activating`, `active`, unvollständigem oder widersprüchlichem Journal niemals
allein anhand des alten Sicherungsdatums zurückschalten. Bei früheren Phasen muss
vor einer manuellen Rückkehr ebenfalls die öffentliche Wartung wirksam sein und
bestätigt werden, dass noch keine neuen Geschäftsdaten angenommen wurden.
Das Journal enthält die tatsächlichen alten Pfade und Kandidatennamen; es ist
kein Anlass, DB-Namen oder Symlinkziele zu raten.

## Reproduzierbare Prüfung

- PostgreSQL-Kontrakte mit ausschließlich `smartplan_check` und
  `smartplan_release_check`: `python -m unittest discover -s backend/online -p test_release.py -v`
  mit `PYTHONPATH=backend`, `SMARTPLAN_TEST_DSN` und passenden `pg_dump`/`pg_restore`.
- Shellablauf: `bash scripts/test-update-flow.sh` nutzt ein kurzlebiges,
  netzloses Docker-Dateisystem mit fiktiven Diensten und echten Dateiwechseln.
- HTTPS-Wartungsrouting: `SMARTPLAN_CADDY_BINARY=<geprüfter-Caddy> python -m unittest discover -s backend/online -p test_release_tls.py -v`
  mit `PYTHONPATH=backend`. TLS wird gegen eine lokale Test-CA geprüft.

Diese Tests führen weder auf der Nutzer-VM noch mit echten Geschäftsdaten
Änderungen aus. Details zu den fiktiven Shellfällen stehen in
[tests/update_flow/README.md](../../../tests/update_flow/README.md).
