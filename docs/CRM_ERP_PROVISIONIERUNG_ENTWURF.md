# Zweite Unternehmensinstanz – additiver Umsetzungsentwurf

Stand: 3. November 2026. Freigegebener Entwurf für R03.04/R11.05 nach Prüfung des
vorhandenen Codes. Der inzwischen implementierte Umfang und die tatsächlichen
synthetischen Nachweise stehen in [CRM_ERP_PROVISIONIERUNG.md](CRM_ERP_PROVISIONIERUNG.md).
Eine reale Bereitstellung ist nicht erfolgt. Die folgenden Abschnitte halten den
ursprünglichen Architektur- und Prüfplan fest.

## Bestehende Grundlage und tatsächliche Lücke

`backend/online/instance.py` bindet eine Datenbank unveränderlich an Instanz-ID,
Host, private Serverablage und Vault-Fingerabdruck. Der HTTP-Start prüft die
Bindung; der Planimport-Worker prüft seine feste Konfiguration. Identisches
`bind` ist wiederholbar, fremde oder teilweise geschriebene Marker werden nicht
übernommen. `test_instance_isolation.py` prüft zwei SQLite-/HTTP-Instanzen;
`test_organization_pg.py` prüft die Bindung einer PostgreSQL-Instanz.

Die Betreiberwerkzeuge sind dagegen an eine bestehende Installation gebunden:

| Datei | Konkrete Bindung / Konsequenz |
| --- | --- |
| `deploy/hetzner/online/install-online.sh` | Nur Erstinstallation unter `/opt/smartplan-online`, `/etc/smartplan-online`, `/var/lib/smartplan-online`, Dienstkonto `smartplan-online`, Datenbank `smartplan_online`, Port 8766. Vorhandene Ressourcen führen zum Abbruch. |
| `update-online.sh`, `manage-online.sh`, `prepare-business-security.sh` | Feste Locks, Units, Pfade und Dienstkonfiguration; Update zusätzlich fester Host. Diese Dateien dürfen nicht durch bloßes Suchen/Ersetzen für eine zweite Firma wiederverwendet werden. |
| `backend/business_schema.py` | Runtime-Schutz, Grants und Ownership erwarten exakt `smartplan-online`/`smartplan-migrator`. Zwei Datenbanken mit demselben Runtime-Benutzer wären keine getrennten Unternehmenszugänge. |
| `backend/online/store.py`, `restore.py`, `release.py` | Migration, Wiederherstellungsrolle, DSN-Prüfung und Security-Vorbereitung enthalten dieselben festen Rollennamen. |
| `backend/online/backup.py` | Wiederverwendbare Funktion mit Zielverzeichnis vorhanden; CLI verwendet bislang einen festen Sicherungspfad. |
| systemd-Dateien im Online-Deployment | API, Import, Sicherung und optionale Antwortzustellung benutzen feste Konten, Pfade und Umgebungsdateien. |

Ein zweiter Hostname oder eine zweite Datenbank allein schließt diese Lücke nicht.
Der erste neue Betriebsweg bleibt eine Firma pro Datenbank und Prozess mit fester
Konfiguration. Ein HTTP-Aufruf erhält keinen Unternehmensselektor.

## Vorgeschlagener Vertrag

Ein neues, ausschließlich vom Betreiber verwendetes Manifest enthält:

- Formatversion, zufällige dauerhafte Instanz-ID, begrenzten ASCII-Kurznamen,
  vollständigen HTTPS-Host, Loopback-Port und exakten Quellcommit;
- abgeleitete eigene Linux-Gruppe/-Benutzer, Runtime-Rolle, NOLOGIN-Owner-Rolle,
  Datenbankname, private Ablage-, Konfigurations-, Sicherungs- und Journalpfade;
- unabhängige Privacy-Installations-ID und Referenzen auf getrennte Schlüsseldateien;
- explizite Module und zunächst deaktivierte optionale Worker/Anschlüsse.

Das Manifest enthält keine Passwörter, API-Token, Vault-Schlüssel oder Fallinhalte.
Pfade und Rollen werden aus dem geprüften Kurznamen unter festen neuen Wurzeln
abgeleitet. Keine Shellfragmente, beliebigen DSN-Optionen oder aus Requests
übernommenen Pfade. Beispielsweise eigene Bereiche unter
`/opt/smartplan-companies/alpha`, `/etc/smartplan-companies/alpha` und
`/var/lib/smartplan-companies/alpha`. Die bisherigen Online-Pfade bleiben reserviert.
Die konkreten Namen sind vor Implementierung gemeinsam festzulegen.

Ein kanonischer Manifest-Hash bindet erzeugte Unit-/Proxy-/Konfigurationsdateien
und den Ablauf. Ein root-eigenes Journal hält ausschließlich Phasen, Ressourcen,
Fingerabdrücke und Prüfergebnisse. Wiederholung desselben Auftrags prüft die
tatsächlichen Ressourcen erneut. Geänderte Parameter, unbekannte vorhandene
Ressourcen, Symlinks, fremde Eigentümer, überlappende Verzeichnisse, Host-/Port-/
Rollen-/Schlüsselkollisionen und unvollständige Geheimnisse führen zum Abbruch.
Weder bestehende Datenbanken noch fremde Units werden automatisch gelöscht,
übernommen oder angehalten.

## Umsetzung in drei prüfbaren Paketen

### P1: Manifest, Plan und Ressourcenprüfung

Neue Dateien `backend/online/provisioning.py` und
`backend/online/test_provisioning.py`: strikter Manifestparser, kanonische
Ressourcenableitung, Kollisionsprüfung gegen das Betreiberinventar und fest
reservierte Bestandsressourcen, deterministischer Plan/Render, Phasenvertrag.
Ausgabe ist ein prüfbares Bundle mit Hashmanifest, keine ausgeführte Shell.
Das Prüfergebnis unterscheidet konfiguriert, lokal geprüft und tatsächlich gestartet.

Ein neuer Wrapper `deploy/hetzner/online/prepare-company.sh` würde ausschließlich
diesen neuen Pfad verwenden. Der erste Entwicklungs-/Abnahmelauf schreibt nur
in ein synthetisches Arbeitsverzeichnis. Er darf weder `systemctl`, `useradd`,
Paketinstallation noch reale Proxy- oder Datenbankänderungen ausführen.

### P2: Tatsächliche unabhängige PostgreSQL-Rollen und Schutzprüfungen

Neues enges Hilfsmodul `backend/online/instance_roles.py` stellt eine unveränderliche,
prozessgebundene Rollenbeschreibung bereit. Bestehende Konfiguration ohne neue
Instanzbeschreibung behält exakt die bisherigen Namen und Schutzprüfungen.
Der neue Betreiberpfad übergibt ausschließlich ein geprüftes Rollenpaar.

Betroffene gemeinsame Stellen: `business_schema.require_runtime_security`,
`apply_runtime_privileges` und Operatorprüfung des Finanz-Restores;
`online.store.migrate`; `online.restore.restore_dump`/Restorepfad;
die eng begrenzten Rollen-/DSN-Prüfer und Security-Vorbereitung in `online.release`.
SQL-Rollen werden mit `psycopg.sql.Identifier` gebunden. Keine bestehenden
Schemas oder Migrationschecksummen ändern, keine generelle Freigabe beliebiger
Rollen und keine Änderung des bestehenden festen Update-CLI.

Pro Firma eigene Runtime-LOGIN-Rolle ohne Superuser/CREATE/CREATEROLE/BYPASSRLS,
eigene NOLOGIN-Owner-Rolle, keine Rollenmitgliedschaft zwischen Runtime und Owner,
kein CONNECT einer anderen Unternehmensrolle auf die Datenbank. Alle Fachobjekte
gehören dem passenden Owner. Die vorhandenen Tabellen-/Spaltengrants und
unveränderlichen Historien bleiben identisch. Ein lokaler PostgreSQL-Operator
erstellt neue Ressourcen; die Anwendung erhält keine Clusterverwaltung.

Die erste Instanzbindung braucht eine gesondert abgesicherte Initialisierungsphase,
weil der private Ablagemarker dem Runtime-Linux-Benutzer gehören muss, die Runtime
im Dauerbetrieb aber nur SELECT auf der Identität erhält. Vorschlag: während alle
neuen Dienste noch gestoppt sind, ausschließlich INSERT auf die leere
Identitätstabelle vorübergehend für den einmaligen vorhandenen `bind`-Befehl
erlauben, danach sofort entziehen und vollständig prüfen. Kein Owner-Passwort im
Runtime-Prozess, keine Mitgliedschaft in der Owner-Rolle. Abbruch hinterlässt die
Instanz gesperrt; erneute Ausführung prüft die Reservierung und entzieht die
temporäre Berechtigung vor Freigabe. Dieser Vertrag ist vor Umsetzung separat
gegen die bestehenden Operator-/Runtime-Tests zu prüfen.

### P3: Einrichtung, Startprüfung und zweifache lokale Abnahme

Neue additive Vorlagen unter `deploy/hetzner/online/companies/` für API,
Planimport, Sicherung und optionalen Antwortworker. Jede Unit verweist auf genau
eine geschützte Konfiguration und eigene State-/Temp-/Lock-Bereiche. Root-eigener
Code darf gemeinsam unveränderlich vorliegen; beschreibbare Bereiche, Sicherungen
und Secrets werden nie geteilt. Private Vault- und Checkpoint-Schlüssel entstehen
exklusiv, werden nicht erneut generiert und nicht im Journal ausgegeben.

Die kontrollierte Reihenfolge wäre:

1. Inventar prüfen und reservieren; Bundle/Quellstand verifizieren.
2. Eigene Konten und private Ressourcen erstellen; fehlende Abhängigkeiten nur
   melden, nicht stillschweigend den vorhandenen Server umbauen.
3. Leere Datenbank explizit migrieren, Rollen härten, Instanz binden, temporäre
   Initialisierungsrechte entfernen und unabhängigen Privacy-Checkpoint initialisieren.
4. Eigenen Owner über den vorhandenen geschützten Eingabeweg anlegen; kein
   Standardpasswort, kein Kopieren der ersten Firma und kein Mailversand.
5. Alle Integrationen/LLM/STT-/Mailzustellungen ohne eigene Freigabe deaktiviert
   halten. Import-Worker erhält eigene Instanz-/Host-Prüfung; weitere Worker müssen
   dieselbe Bindung vor ihrem ersten Auftrag bestätigen.
6. Loopback-Readiness, tatsächliche MFA, getrennte Dateien und minimale Fachvorgänge
   prüfen. Ein Erfolg der lokalen Prüfung aktiviert noch keinen öffentlichen Host.
7. Eigene Sicherung und Wiederherstellung in eine zusätzliche leere Datenbank
   prüfen, einschließlich Instanzbindung, fehlendem/fremdem Privacy-Checkpoint,
   widerrufenen Sitzungen, blockierten Zustellungen und Finanzfreigabe.
8. Erst ein späterer ausdrücklich autorisierter Betreiberlauf könnte genau den
   neuen Host nach geprüfter Proxy-Konfiguration freischalten. Bestehende Hosts
   müssen bei Fehlern unverändert weiterlaufen.

## Lokale Testmatrix und Abschlusskriterium

Zwei synthetische Firmen mit getrennten echten PostgreSQL-Rollen/Datenbanken und
zwei lokalen API-Prozessen. Keine reale DNS-/TLS-/Hetzner-Bestellung und keine
Anbieter- oder E-Mail-Aufrufe. Die bestehende einwegfähige PostgreSQL-Testumgebung
wird nur nach expliziter Slotübergabe verwendet.

- Plan/Render exakt wiederholbar; konkurrierende Aufträge und Abbruch nach jeder
  Phase mit erneutem Start; Fremd-/Teilressourcen werden nicht überschrieben.
- Linux-Dateirechte und fremde Ablagen/Schlüssel: Zugriff ausdrücklich verweigert;
  der Test darf keine Prozessisolation behaupten, wenn er nur mit derselben UID läuft.
- Runtime A kann Datenbank B nicht verbinden, Owner B nicht übernehmen und dort
  weder lesen noch schreiben; spiegelbildliche Prüfung für B.
- Gleiche Benutzer-E-Mail und gleiche Objekt-IDs: unabhängige MFA, Sitzungen,
  Dateien, Projekte, Suche, Assistent-/Sprachmetadaten und Hintergrundaufträge.
- Falscher Host, DB, Instanz-ID, Marker, Schlüssel oder Worker-Konfiguration sperrt
  den Start beziehungsweise die Verarbeitung; bestehende Firma bleibt verfügbar.
- Restore einer Firma verändert die andere nicht; fremdes Backup/Checkpoint/
  Ablage-Mapping wird nicht als eigenes freigegeben.
- Bestehende Legacy- und Rollen-/Finanz-/Privacy-Regressionen unverändert grün.

Erst nach diesen Nachweisen kann die zweite lokale Unternehmensinstanz als
implementiert und synthetisch abgenommen gelten. Öffentliche Bereitstellung,
reale DNS/TLS-Verwaltung, Betreiberzugriff, getrenntes verschlüsseltes Offsite-Backup,
Last-/Monitoringabnahme und Schlüssel-/Hostrotation bleiben eigenständig zu prüfen.
Sie sind keine Rechtfertigung, die unabhängig implementierbaren Provisionierungs-
und Isolationsprüfungen auszulassen.
