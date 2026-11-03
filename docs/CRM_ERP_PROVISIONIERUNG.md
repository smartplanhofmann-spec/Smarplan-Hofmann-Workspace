# Getrennte Unternehmensinstanzen vorbereiten und prüfen

Stand: 3. November 2026. P1–P3 des freigegebenen
[Entwurfs](CRM_ERP_PROVISIONIERUNG_ENTWURF.md) sind als additive Betreiberwerkzeuge
implementiert und lokal mit synthetischen Firmen geprüft. Es wurde keine reale
Unternehmensinstanz, kein Hostkonto und keine öffentliche Route bereitgestellt.

## Feste Trennung

Ein Manifest beschreibt genau eine Firma mit dauerhaftem Kurznamen, Instanz-ID,
HTTPS-Host, Loopback-Port, Quellcommit und unabhängiger Privacy-Installations-ID.
Es enthält keine Zugangsschlüssel. Aus dem Kurznamen werden eigene Bereiche unter
`/opt/smartplan-companies`, `/etc/smartplan-companies`,
`/var/lib/smartplan-companies` und ein geschütztes Betreiberjournal unter
`/var/lib/smartplan-company-operator` abgeleitet.

Neue Firmen benutzen die Runtime-Rolle **und gleichnamige Linux-Identität**
`sp_<slug>_run`, die NOLOGIN-Owner-Rolle `sp_<slug>_own` und die Datenbank
`sp_<slug>`. Damit funktioniert der vorgesehene PostgreSQL-Unix-Socket mit
Peer-Anmeldung ohne Passwort oder pauschale `pg_ident`-Umschreibung.

`SMARTPLAN_INSTANCE_ROLES_FILE` verweist auf eine root-eigene, gegen fremde
Änderungen geschützte JSON-Datei. Ihr Inhalt und ihre Elternverzeichnisse werden
geprüft; Instanz-ID und abgeleitete Rollen müssen zur festen Prozesskonfiguration
passen. HTTP-Anfragen wählen weder Firma noch Rolle oder Datenbank. Ohne diese
neue Einstellung gelten unverändert die bisherigen Rollen
`smartplan-online`/`smartplan-migrator`.

Neue Runtime-Rollen dürfen keine andere Rolle übernehmen, keine fremde Firmen-
oder Legacy-Firmendatenbank verbinden und keine fremden nicht privilegierten
LOGIN-Rollen auf ihrer Datenbank zulassen. Bestehende falsche Grants werden
abgewiesen. Sämtliche vorhandenen Schutzrechte für Fachhistorien bleiben bestehen.
Migration und Wiederherstellung prüfen den eigenen Datenbanknamensraum und eine
bereits vorhandene Instanz-ID **vor** einer Schemaänderung. Ein in die falsche
Firmenkopie eingespielter Dump wird dadurch vor der Freigabe gesperrt.

## Plan und private Vorbereitung

Das Beispielmanifest und der Betreiberweg stehen unter
`deploy/hetzner/online/companies/README.md`. Der reine Plan benötigt keine
Datenbank oder Root-Rechte:

```sh
PYTHONPATH=backend python -m online.provisioning plan --manifest MANIFEST.json
```

`bundle` erzeugt eine exakte Reservation, deterministische geschützte Dateien und
deren Hashmanifest in einem eigenen privaten Verzeichnis. Kollidierende Hosts,
Ports, Rollen, Instanz-/Privacy-IDs, veränderte Wiederholungen, fremde Artefakte und
unsichere Pfade werden abgewiesen. Bei einer identischen Wiederholung werden
bestehende Artefakte geprüft. Die neuen systemd-/Proxy-Vorlagen werden zentral in
`online.provisioning.render` erzeugt und damit zusammen mit dem Parser getestet.

Der zusätzliche Wrapper `deploy/hetzner/online/prepare-company.sh` benötigt einen
bereits bereitgestellten, root-eigenen Release. Er prüft mit dem isolierten
System-Python den **gesamten** Code-/Runtimebaum einschließlich Abhängigkeiten,
Dateirechten und Links, bevor er Anwendungscode mit Betreiberrechten importiert.
Ein fester administrativer PATH, isolierte Kindprozessumgebung und
`PYTHONSAFEPATH=1` verhindern fremde Programm- oder Importauswahl.
`SOURCE_COMMIT` dokumentiert die Betreiberzuordnung zum Quellstand; diese Datei
allein ist keine kryptografische Inhaltsattestierung des Git-Commits.

Die ausdrücklich gestartete Aktion `prepare` reserviert Ressourcen unter einer
gemeinsamen Betreibersperre, prüft gestoppte eigene Units, legt das eigene
Dienstkonto und getrennte Konfigurations-/State-Verzeichnisse an, erstellt
unabhängige private Schlüssel und bereitet die eigene neue Datenbank vor.
Rollen und Datenbank tragen exakt an das Manifest gebundene Reservationsnachweise.
Vorhandene fremde Ressourcen werden nicht übernommen; aktive Datenbanknutzer
verhindern eine wiederholte Migration. Ein Abbruch zwischen `CREATE DATABASE`
und ihrer Quittung benötigt ausdrückliche Betreiberprüfung, keine automatische
Übernahme einer unbestätigten Datenbank.

Die erste Instanzbindung erhält ausschließlich während des einen Bindungsschritts
INSERT auf die leere Identitätstabelle. Der Vault-Schlüssel bleibt beim Runtime-
Linux-Benutzer; der PostgreSQL-Operator bekommt keine Schlüsselbytes. INSERT wird
im Fehlerpfad und beim Wiederanlauf nach positiv geprüftem eigenen DB-Nachweis
entzogen. Im Dauerbetrieb besitzt die Runtime nur SELECT auf der Firmenidentität.
Danach werden Checkpoint, Datenbankrollen und tatsächliche Ablagebindung geprüft.
Private Schlüssel werden bei Wiederholung nicht ersetzt. Fehlt ein bereits
bestätigter Schlüssel, bleibt die Vorbereitung gesperrt.

## Owner und privater Start

Die Aktionen sind getrennt und nur durch einen ausdrücklich handelnden Betreiber
aufrufbar:

```sh
bash deploy/hetzner/online/prepare-company.sh prepare MANIFEST.json
bash deploy/hetzner/online/prepare-company.sh init-owner MANIFEST.json owner@example.test
bash deploy/hetzner/online/prepare-company.sh check MANIFEST.json
bash deploy/hetzner/online/prepare-company.sh start-private MANIFEST.json
```

Das Owner-Passwort wird über den vorhandenen verdeckten Eingabeweg festgelegt;
es gibt kein Standardpasswort und keine Übernahme der ersten Firma. MFA wird beim
ersten tatsächlichen Login eingerichtet. Unternehmensbedarf und Modulwahl werden
anschließend in der bestehenden Firmenkonfiguration erfasst. Es wird weder ein
Steuerprofil noch ein fremder Datenbestand vorbefüllt.

`start-private` prüft eigene Units ohne versteckte Umgebungs-/Drop-in-Overrides,
Owner, Runtime- und Ablagebindung. Ein bereits belegter Port wird vor einem neuen
Start abgewiesen. Nach Readiness muss die weiterhin aktive eigene systemd-Unit
mit ihrer tatsächlichen MainPID auch den geprüften Loopback-Socket besitzen.
Eine ähnlich antwortende fremde Anwendung kann die Instanz nicht bestätigen.
Unautorisierte Projektabfrage muss 401 liefern. Danach folgen die eigene lokale
Sicherung und ihr Timer; der optionale Planimport benötigt zuvor seinen
installierten isolierten Worker und eine erfolgreiche Doctor-Prüfung.

Fehler stoppen nur die in diesem Start neu gestarteten eigenen Units. Der
Wrapper verändert keine bestehende Online-Installation und lädt keine gemeinsame
öffentliche Proxy-Konfiguration neu. Der erzeugte Caddy-Abschnitt bleibt ein
separat zu prüfendes Artefakt. Mail-, Zahlungs-, LLM-/STT- und weitere Anbieter-
Konfigurationen werden nicht aus einer anderen Firma übernommen oder aktiviert.

## Sicherung und Abnahmegrenzen

Die Sicherung nutzt die eigene Runtime-Rolle und den privaten Firmenpfad. Restore
erfolgt in einer anderen leeren Datenbank desselben Firmenbereichs. Fehlender oder
fremder Privacy-Checkpoint verhindert die Freigabe; alte Sitzungen und ungewisse
Außenaktionen werden nicht wieder aktiviert. Der notwendige Finanzabgleich bleibt
nach Restore ausdrücklich offen. Alte Installations-/Update-Skripte wurden nicht
in generische Mehrfirmen-Skripte umgeschrieben. Host-/Schlüsselrotation und ein
automatischer Upgrade-Orchestrator für die neuen Firmenbereiche sind gesonderte
Betreiberverfahren, keine Wirkung des Erstbereitstellungsbefehls.

Nachgewiesen wurden:

- **29 lokale Guard-/Domänen-/Reviewfälle:** 15 Provisionierungsfälle, zehn
  bestehende Legacy-ReleaseGuards und vier unabhängige Gegenproben; darunter
  unsichere Eltern, transitive Code-/Dependencyrechte, externe Verzeichnislinks
  und tatsächlicher Socketbesitz eines gesonderten Prozesses.
- **3 echte PostgreSQL-Fälle:** zwei unabhängige Firmenrollen/Datenbanken und
  API-Prozesse mit tatsächlicher MFA/HTTP, fremde Sitzungen/Objekte, getrennte
  Dateien bei gleichen IDs, Owner-/Runtime-Mitgliedschaft, fremde und Legacy-
  CONNECT-Grants, Wiederholung, aktive Zielverbindungen vor Migration,
  Erstbindungsabbruch nach echtem GRANT mit anschließendem Entzug, direkte falsche
  Migrationsdatenbank, tatsächliches `pg_dump`/Restore, Fremddump und unabhängige
  Checkpoint-/Finanzfreigabegrenzen. Letzter Lauf: 12,990 Sekunden.
- **4 bestehende PostgreSQL-Release-/Restorefälle:** Runtime kann keine
  unveränderlichen Belege oder SQL-Guards verändern; echtes Schema-6-Upgrade
  erhält alte Tabellen; ausdrücklicher Restore erhält finale Geschäftsdaten und
  setzt nur alte Zugänge zurück; privilegierter Restore liest keinen Runtime-
  Schlüssel und die Runtime übernimmt neuere Privacy-Entscheidungen.
  Abschließender Lauf am eingefrorenen P3-Stand: **4/4 in 16,194 Sekunden**,
  ohne Fehler oder Auslassung. Protokoll: `work/verification/provisioning-legacy-pg.log`.
- **1 echter Linux-UID-Test:** numerische UIDs 24001/24002 im kurzlebigen Container
  ohne Netz, Host-Mounts oder persistente Volumes können fremde private Dateien
  weder lesen, schreiben, löschen noch umbenennen. Eigener Zugriff funktioniert;
  beide Originale bleiben unverändert. Lauf: 3,178 Sekunden.
- Shellsyntax, Python-Kompilierung und gezielter Diff-Check ohne Befund.

Die zwei lokalen API-Prozesse verwenden dieselbe Fixture-UID; die gesonderte
Containerprüfung belegt die Dateirechte mit unterschiedlichen UIDs. Zusammen ist
dies keine Behauptung einer bereits ausgeführten kompletten systemd-Installation
auf einem echten Kundenserver. In der Cloud haben Systemverzeichnisse abweichende
abgebildete UIDs. Lokale Dateipositivtests injizieren deshalb ausschließlich im
Testcode eine private Trust-Root; die produktiven UID-0-Prüfungen bleiben streng.

Reale DNS/TLS-Freigabe, das konkrete Betriebssystem-/Proxy-Setup, verschlüsseltes
Offsite-Backup, Monitoring, Lastprüfung und organisatorische Zuständigkeit sind
vor öffentlichem Betrieb gesondert abzunehmen. Lokale Sicherungen und erfolgreiche
synthetische Tests ersetzen diese Betriebsnachweise nicht.

Läufe: `work/verification/provisioning-unit.log`, `provisioning-pg.log` und
`provisioning-uid.log`. Tests: `backend/online/test_provisioning.py`,
`test_provisioning_pg.py`, `test_provisioning_uid.py` und die unabhängige
`test_provisioning_security_review.py`. Der UID-Test benötigt ausdrücklich
`SMARTPLAN_UID_CONTAINER_TEST=1`. Das reservierte lokale PG-Fenster wird zwischen
Tests schriftlich übergeben; der normale Unitlauf startet keine Datenbankdienste.
