# Unabhängige Prüfung des neuen Unternehmens-Rollenvertrags

Stand 03.11.2026. Interne Prüfung von P1–P3 aus
[CRM_ERP_PROVISIONIERUNG_ENTWURF.md](CRM_ERP_PROVISIONIERUNG_ENTWURF.md).
Dies ist keine abgeschlossene externe Sicherheitsabnahme und keine öffentliche
Bereitstellung. Gemeinsame Produktionsdateien werden durch den zuständigen
Implementierungsagenten geändert; diese Prüfung liefert unabhängige Befunde
und gezielte Nachweise.

## Reproduzierter und behobener Dateisystembefund

`write_bundle` akzeptierte zunächst ein privates Zielverzeichnis mit Modus 0700
unter einem nicht-sticky, allgemein beschreibbaren Elternverzeichnis (0777).
Eine andere UID könnte dessen Verzeichnisnamen umbenennen oder ersetzen;
nachfolgende pfadbasierte Betreiberzugriffe waren deshalb nicht ausreichend
an die geprüfte Reservierung gebunden.

Die unabhängige Regression
[test_provisioning_security_review.py](../backend/online/test_provisioning_security_review.py)
forderte Ablehnung vor dem ersten Schreibzugriff. Sie schlug gegen den
ursprünglichen Stand tatsächlich fehl (1 Fall, 0,067 s), da keine Ablehnung
erfolgte. Nach Ergänzung der Elternprüfungen bestand sie (1/1). Es wurden nur
synthetische temporäre Verzeichnisse der eigenen UID verwendet; keine fremden
Dateien oder privilegierten Prozesse wurden angegriffen.

Der frühere Lauf aus zehn Manifest-/Bundle-/Rollenfällen und dieser
unabhängigen Regression bestand **11/11 in 0,009 s**, ohne Skip. Der aktuelle
unabhängig ausgeführte Nachlauf aus inzwischen 15 Manifest-/Hostvertragsfällen,
den zehn bestehenden `online.test_release.ReleaseGuards` und vier eigenen
Gegenproben bestand **29/29 in 0,051 s**, ohne Skip. Frühere Zwischenläufe
sind darin enthalten und werden nicht addiert.
Der Dateisystemfall enthält jetzt außerdem einen erfolgreichen Kontrollpfad
unter derselben synthetischen Testwurzel. Eine Ablehnung allein wegen des
gemappten Cloud-Rootbesitzers kann dadurch keinen Erfolg vortäuschen. Produktion
erwartet geschützte UID-0-Pfade. Die Cloud stellt `/` und `/tmp` mit gemappter
UID 65534 bereit; positive lokale Dateifixtures verwenden deshalb eine
ausdrücklich injizierte private Testwurzel. Der produktive Konfigurationsleser
und die CLI erhalten diesen Testparameter nicht aus Requests oder Umgebungsdaten.
Das ist kein Nachweis realer Linux-Benutzertrennung auf dem späteren Server.

Protokolle liegen unter `work/verification/provisioning-security-review-*.log`.

## Weitere konkrete Reviewpunkte

| Punkt | Erforderliche Grenze | Stand der Nachprüfung |
|---|---|---|
| Fremde Rollenmitgliedschaft / CONNECT | Neue Runtime darf keine andere Rolle übernehmen; weder andere Firmenrolle zur eigenen DB noch eigene Rolle zur fremden Firma | Guards vorhanden; echte PG-Gegenproben für fremde Owner-/Runtime-Mitgliedschaft und CONNECT in beide Richtungen bestanden |
| Bestehende Legacy-Firma | Neue Runtime muss auch gegenüber der bestehenden `smartplan_online` beziehungsweise deren Ownerbereich getrennt sein | Ausgehende Prüfung berücksichtigt Legacy-Ownerbereiche; echte Driftgegenprobe mit zusätzlicher Legacy-Owner-Datenbank und fremdem CONNECT bestanden |
| Fremdes Restoreoriginal | DB-Namensraum und gespeicherte Instanz-ID müssen zum festen Rollenobjekt passen, bevor Restore als verifiziert gilt | `PostgresOffice`, `migrate` und `complete_restore` prüfen dies nun; bewusster Fremddump in leerem isolierten Ziel wurde tatsächlich abgewiesen |
| Unix-Peer-Anmeldung | Linux-Dienstkonto und PostgreSQL-Runtime müssen ohne unkontrollierte globale Mappingänderung übereinstimmen | Neue Namen lauten beidseitig `sp_<slug>_run`; Manifest-/Renderfall bestanden |
| Wiederholte DB-Vorbereitung | Laufende Dienste dürfen nicht erst nach einer Migration erkannt werden | Echte aktive PG-Verbindung verhindert die Vorbereitung; Test prüft zusätzlich, dass `migrate` dabei nicht aufgerufen wird |
| Temporäres Bindungs-INSERT | Nach bestätigter eigener Reservierung müssen auch Grants eines abgebrochenen früheren Versuchs vor weiteren Prüfungen entzogen werden | Vorab-/Finally-REVOKE vorhanden; PG bestätigt Entzug nach modelliertem Prozessabbruch und anschließender aktiver-Verbindungs-Ablehnung. Auch tatsächlich gewährtes INSERT auf einer neuen leeren Identität wird nach Binderfehler entzogen; Identität bleibt leer |
| Direkte Migration | Auch der direkte Betreiberaufruf muss fremden DB-Namensraum/Instanz-ID vor erster Mutation ablehnen | Prüfung vor CREATE/Upgrade ergänzt; sowohl fremde Identität im eigenen Zielnamensraum als auch direkter A-Rollen/B-DB-Aufruf tatsächlich abgewiesen |
| Transitive Programmabhängigkeiten | Auch importierte Module und installierte Python-Abhängigkeiten müssen vor Betreiberaufrufen unveränderlich sein | Die zunächst auf einzelne Dateien beschränkte Prüfung wurde durch `protected_tree` ergänzt. Zwei unabhängige Dateisystemfälle bestätigen geschützte Kontrollbäume und verweigern beschreibbare Module/Dependencies sowie externe Verzeichnislinks |
| Belegter Loopback-Port | Die Antwort eines bereits vorhandenen anderen HTTP-Dienstes darf keine erfolgreiche eigene Einrichtung vortäuschen | Freier Port wird vor neuem Start geprüft. Nach Readiness und vor Erfolgsquittung muss der Socket-Inode tatsächlich zur aktiven eigenen Unit-PID gehören. Unabhängiger Test mit echtem separatem Loopback-Prozess akzeptiert dessen PID und verweigert eine behauptete fremde PID |
| Privilegierte Programmauswahl | Root-Unterprozesse dürfen keinen ungeschützten geerbten PATH oder Python-Suchpfad verwenden | Feste administrative Umgebung und isolierter System-Python vor erstem Releaseimport; gezielter Domainfall verweigert die Übernahme manipulierter Umgebungswerte |

Die vorhandenen Legacy-Rollennamen und ihre bisherigen Prüfungen bleiben der
Standard ohne neue Firmenkonfiguration. Neue Rollen werden aus einem geprüften,
unveränderlichen Rollenobjekt beziehungsweise einer geschützten Datei abgeleitet;
ein HTTP-Unternehmensselektor oder eine Ableitung aus einem untrusted DSN ist
nicht Bestandteil des Vertrags.

## Tatsächlicher PostgreSQL-Nachweis

Der Implementierungsagent führte `online.test_provisioning_pg` nach den
gezielten Ergänzungen erfolgreich aus: **3/3 in 12,990 s**, ohne Skip.
Diese unabhängige Prüfung hat anschließend sowohl
den Testcode als auch `work/verification/provisioning-pg.log` gelesen. Es wurden
zwei zufällig benannte eigene Firmen mit eigenen SQL-Rollen/Datenbanken und
zwei echten HTTP-Prozessen aufgebaut. Identische Owner-E-Mail-Adressen erhalten
getrennte MFA-/Sitzungszugänge; fremde Tokens und Projekt-IDs funktionieren nicht.
Dieselben Dateischlüssel führen in den getrennten Ablagen zu getrennten Bytes.
Beide API-Prozesse laufen hierbei mit derselben Cloud-UID; dieser Test allein
belegt keine Linux-Benutzertrennung.

Das tatsächliche Dump/Restore bleibt bis zur richtigen externen
Privacy-Checkpoint-Prüfung gesperrt. Fehlender und fremder Checkpoint werden
abgewiesen; nach richtigem Checkpoint bleibt der Finanzabgleich ausdrücklich
erforderlich. Ein absichtlich fremdes Backup wird nicht als eigene Firma
geöffnet oder migriert. Die andere Firma behält ihre Identität.

Zusätzlich liegt `work/verification/provisioning-uid.log` vor: **1/1 in 3,178 s**.
Der dazu gelesene Containerfall läuft ohne Netzwerk, Host-Mounts oder persistente
Volumes. Zwei tatsächlich verschiedene UIDs können jeweils ihre eigene Datei
lesen/schreiben, aber die fremde private Ablage weder lesen, beschreiben,
löschen noch umbenennen. Das ist ein tatsächlicher Dateirechtenachweis im
Wegwerfcontainer, weiterhin kein Nachweis einer real installierten
Systemd-/PostgreSQL-Peer-Umgebung beim späteren Betreiber.

Die anschließende Regression der **bestehenden** PostgreSQL-Betreiberwege
bestand zusätzlich mit **4/4 in 16,194 s**, ohne Skip. Das gelesene Protokoll
`work/verification/provisioning-legacy-pg.log` belegt Runtime-/Archivschutz,
echtes Schema-6-Upgrade, geschäftsdatenbewahrenden Restore und die Trennung
zwischen privilegiertem Restore, Runtime-Schlüssel und neuerem Privacy-Checkpoint.
Der Prüflauf wurde vor dem Cloud-Neustart vollständig beendet; ein lediglich
angefangener Lauf wird damit nicht als erfolgreich ausgegeben. SHA-256 des
Protokolls: `53fc09038271c09759adbf0d947900e66187448691e7016f469284a58ce82f10`.
Diese vier Legacy-Fälle sind zusätzlich zu den drei neuen Zweifirmen-Fällen
angegeben; sie sind keine Wiederholung einer unabhängigen externen Abnahme.

## Grenzen dieser Prüfung

Die konkret gemeldeten Codebefunde und angeforderten Gegenproben aus der
Tabelle sind im geprüften Stand geschlossen. Ein echter separater Testprozess
mit Loopback-Socket und `/proc`-Inode wurde ausgeführt; dessen Systemd-Status
und PID-Ausgabe sind im Test ausdrücklich simuliert. Der Socketfall benötigte
die Freigabe lokaler Prozesskommunikation außerhalb der standardmäßigen
Netzsandbox; der erste eingeschränkte Aufruf konnte keinen Socket öffnen.

`SOURCE_COMMIT` ist eine geschützte Betreiberzuordnung zum vorbereiteten
Release. Die Prüfung des vollständigen Baums belegt Besitzer-/Schreibschutz,
aber keinen reproduzierbaren Build oder Inhaltsvergleich mit einem externen
Quellrepository. Diese unterschiedlichen Eigenschaften werden nicht gleichgesetzt.

Ein vollständig ausgeführter Hostlauf mit echten Systemd-Units, eigenen
Linux-Konten, Unix-Peer-Anmeldung und kontrolliertem Wiederanlauf bleibt
ein eigener Betriebsnachweis. Gleiches gilt für öffentliche DNS/TLS-Freischaltung
und unabhängige externe Sicherheitsprüfung. Diese Prüfung installiert oder
aktiviert keinen öffentlichen Unternehmenshost.
