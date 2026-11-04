# R03.04 / Abnahme A: aktuelle technische Unternehmensisolation

Stand: 04.11.2026. Arbeitsbaum `/workspace/smartplan-company-isolation-20261104`,
Basis `2e2ed5ca33b928216b940c6334cdfbbca0a14c27`.

## Auftrag und vorhandene Nachweise

Das unveränderte Gesamtziel verlangt getrennte Unternehmensdaten,
Einstellungen, Originaldateien, Suchkontexte, KI-Kontexte und Hintergrundjobs.
Die aktuelle Anforderungsmatrix führt R03.04 noch offen und Abnahme A teilweise.
Diese Prüfung ergänzt konkrete technische Lücken und tatsächliche Nachweise;
eine externe unabhängige Sicherheitsprüfung und produktive Hostabnahme bleiben
gesondert. Keine Produktivinstallation oder Kontaktaufnahme ist beauftragt.

Vorhanden und zuerst gelesen: `CRM_ERP_INSTANZEN.md`,
`CRM_ERP_PROVISIONIERUNG.md`, der unabhängige Provisionierungsreview,
`online/test_instance_isolation.py`, `online/test_provisioning_pg.py`,
`online/test_provisioning_uid.py` und die aktuellen Events-/Workerpfade.
Die vorhandenen zwei PostgreSQL-Datenbanken mit getrennten Runtime-/Ownerrollen,
echten HTTP-Prozessen und MFA sowie absichtlich fremdem Restore werden nicht
als neue Implementierung ausgegeben. Die separate UID-Abnahme belegt bisher
Dateirechte im Wegwerfcontainer, keine installierte produktive Systemd-Umgebung.

## Arbeitsschritte

1. Aktuelle Pfade für Dateien/Originaldownloads, Suchlisten, Assistenten,
   Event-/Importworker und Unternehmens-/Jahresexporte den bereits vorhandenen
   Grenzen zuordnen. Zweifirmen-Nachweislücken und Produktfehler unterscheiden.
2. Konkrete Gegenfälle in neuen separaten Tests reproduzieren. Bei einem
   Produktfehler roten Stand und Quellenhash sichern, engen Fix ausführen und
   dieselben Fälle unverändert nachprüfen.
3. Tatsächliche zwei lokale Laufzeitinstanzen mit synthetischen unterschiedlichen
   Originalen und frischen MFA-Zugängen prüfen. Fremde Tokens/IDs/Quittungen und
   gleiche Objektkennungen in getrennten Datenbeständen berücksichtigen.
4. PostgreSQL-Rollen-/Runtimekette erst nach expliziter Freigabe des exklusiven
   Testclusters 55433 ergänzen. Neue Datenbanken ausschließlich aus eigenen
   zufälligen Testnamen; keine bestehende Restore-Zieldatenbank überschreiben.
5. Gezielte Altregressionen, dauerhafte Evidenz und Hashhandoff. Anforderungen
   erst nach wirklichen Nachweisen präzisieren; technische und produktive
   Restgrenzen ausdrücklich erhalten.

## Konkreter Befund: verpflichtende CI-Provisionierung erreicht ihren Guard nicht

`checks.yml` leitete den eigenen Wegwerf-PostgreSQL über Hostport 5432 weiter und
verwendete diesen Port im `SMARTPLAN_TEST_DSN`. Die bereits registrierten
Provisionierungstests rufen dagegen den tatsächlichen
`online.provisioning._operator_dsn(..., test_mode=True)` auf. Dieser erlaubt
ausdrücklich nur Loopback, `smartplan_check` und Port 55433. Somit waren diese
Tests in der konfigurierten CI vor einer Datenbankverbindung blockiert.

Der neue `test_company_isolation_ci.py` liest die tatsächliche CI-Konfiguration
und ruft diesen bestehenden Guard unverändert auf. Er scheiterte nachweislich
vor dem Fix; Log und damalige Workflowbytes sind separat erhalten. Der enge Fix
ändert ausschließlich den Hostport des Wegwerf-Service und seinen DSN auf 55433.
Die Produktgrenze wird nicht gelockert. Derselbe Test besteht anschließend.
Außerdem sind die neuen Dateien über `test_company*isolation*.py` im bestehenden
Online-CI-Job registriert. Die tatsächliche SQLite-Queue-/Parserkette ist im
vorhandenen `plan-import.yml`-Job zusätzlich verpflichtend ausgewählt: eigener
Parserinterpreter, bereits gesperrte Online-Abhängigkeiten und explizites
`SMARTPLAN_TEST_PARSER_PYTHON`. Der reine PostgreSQL-Parserfall bleibt dort
gesondert; er wird durch den tatsächlichen lokalen PostgreSQL-Lauf belegt.
Ein tatsächlicher Lauf bei GitHub wurde nicht ausgelöst.

## Bestätigter Produktfehler: native Daten bei erhaltener Navigation

Der unabhängige Review verwendete gespeicherte **tatsächliche Antworten der
zwei lokalen HTTP-/MFA-Instanzen** in Flutter. Fünf unveränderte Gegenfälle
scheiterten vor dem Fix: private Alpha-Chatdaten blieben nach Austausch der
Elternsession durch die Beta-Session sichtbar; eine gehaltene Alpha-Antwort
befüllte anschließend die Beta-Ansicht; ein privater Originaldialog überlebte
den Sessionwechsel und ebenso das Entfernen der Seite bei erhaltenem Navigator;
eine aktive Sprachaufnahme wurde beim Session-/Hostwechsel nicht abgebrochen.
Der Recorder ist dabei ein kontrollierbares lokales Testdouble; es fand kein
Mikrofon- oder externer Anbieterzugriff statt. Die serverseitige Prüfung hatte
keinen fremden Datenzugriff freigegeben. Es handelt sich um lokale Restanzeige
und veralteten Vorgangskontext, nicht um eine behauptete serverseitige Querfreigabe.

Die ursprünglichen Seiten-/Sprachdateien, Teststände und roten Logs bleiben
bytefest im unabhängigen Evidenzordner. `business_assistant.dart` bindet nun beim
Elternwechsel alte Listener ab und neue an, löscht private Zustände, erfasst
eigene Dialogrouten und entfernt sie bei Sessionwechsel/Seitenabbau sowie
bekanntem Rechteverlust oder Hintergrundwechsel. Eine darüberliegende fremde
Route bleibt erhalten. Detailantworten und Fehler müssen weiterhin zur
ursprünglichen Sitzung, zum Projekt und zur laufenden Ansicht gehören.
`business_speech.dart` bindet die Aufnahme an die ursprüngliche Session und
verwirft Aufnahme/Entwurf bei Austausch ihrer Sitzung, Quelle oder
Anbieterkonfiguration. Ein unbestätigter Auftrag wird dadurch nicht zu einem
neuen Auftrag der anderen Firma.

Der erste eigene Nachlauf bestand **23/23**. Der unabhängige Nachtest bestätigte
danach einen sechsten engen Gegenfall: Ein Hintergrund-/Resumewechsel während
der noch gehaltenen ersten Capabilities-Antwort konnte anschließend neue
Fachabfragen und alte Chatdaten auslösen. Dieser rote Zwischenstand ist
ebenfalls separat erhalten. Der Ladeauftrag bindet deshalb nun bereits vor
seiner ersten Rechteabfrage den Vordergrundzustand; ein tatsächlicher
Hintergrundwechsel macht auch diese erste Phase dauerhaft ungültig.

Aktueller eigener Nachlauf: **90/90**, einschließlich aller zwölf unabhängigen
Isolationsfälle sowie bestehender Assistant-/Speech- und Eventsfälle. Analyse
der zwei Produktdateien und der unabhängigen Testdatei ohne Befund. Der letzte
unabhängige Hashhandoff wird noch erstellt; ursprüngliche Rotstände bleiben
unverändert erhalten.

## Neue tatsächliche Abnahmeketten

`online.test_company_isolation_current` startet je Fall zwei unabhängige
Werkzeug-Serverprozesse mit separater SQLite-Datenbank, Vault-Schlüssel,
gebundenem Ablagepfad, Host und Instanz-ID. Beide verwenden dieselbe synthetische
Owner-E-Mail, aber tatsächliche separate MFA-Anmeldungen. HTTP-Anfragen laufen
über echte Loopback-Sockets. Ein `Flask.test_client` ersetzt diese Strecke nicht.

| Fall | Positive Strecke und konkrete fremde Gegenrichtung |
|---|---|
| Katalog, Suche, vollständiger Export | Gleichnamige Originaldatei und gleicher Artikelcode sowie dieselbe Import-/Exportnonce in beiden Firmen; eigene Bytes und akzeptierte Replayquittung stimmen; Fremdtoken 401, Fremdoriginal/-historie404, fremder Suchmarker ohne Treffer, fremdes Exportobjekt404 und fremde Instanz im Exportauftrag 409. Alle entpackten Archiveinträge werden auf den fremden Datenmarker geprüft; komprimierte ZIP-Bytes allein wären kein genügender Negativnachweis. |
| Kontexte und Ereignisaktionen | Gleiche explizite Regel-ID und dieselben Kontext-/Regel-/Scannonces, aber unterschiedliche tatsächliche Projekte, Tasks und Verantwortliche. Fremde Kontext-, Task-, Plan- und Laufreferenzen liefern 404. Eigene freigegebene Aktion erzeugt tatsächlich genau einen Folge-Task, ihr Replay bleibt identisch. Eine Ausführung des eigenen Plans beim anderen Server scheitert. |
| Private Personaloriginale | Gleichnamige PDF-Datei und gleiche Uploadnonce, eigene echte Mitarbeiterprofile. Ursprüngliche Bytes bleiben erhalten. Fremde Tokens/Datei-/Mitarbeiterreferenzen scheitern. Ein zusätzlicher Buchhaltungszugang erhält ausdrücklich Personal-Leserecht; unmittelbar nach dessen Entzug liefert derselbe noch angemeldete Token für Liste und Download 403. |
| Importwarteschlangen | Gleichnamige echte PNG-Dateien mit unterschiedlichen Bytes und derselben Uploadnonce; tatsächliche HTTP-Chunkannahme und Queue. Ein zusätzlicher Workerprozess pro Firma ruft die feste Workerbindung und den wirklichen lokalen Parser auf. Ergebnis und unverändertes Original sind an den eigenen Hash gebunden. Nach Verarbeitung der ersten Firma bleibt die zweite Queue ausdrücklich `queued`; Fremdprojekt/-job/-token geben keinen Zugriff. |

Erster kompletter lokaler Lauf: **4/4 bestanden, 9,993 Sekunden**. Der tatsächliche
Parser verwendet für diese ausschließlich synthetischen Daten ausdrücklich
`DevelopmentRunner`; dieser Lauf ist kein Kernel-Sandboxnachweis. Die gesonderte
bestehende Produktions-Sandbox-/Systemd-Abnahme bleibt ihr eigener Vertrag.
Ohne ausdrücklich gesetztes `SMARTPLAN_TEST_PARSER_PYTHON` wird nur dieser
Parserfall als nicht ausgeführt gemeldet; die drei anderen Ketten laufen regulär.

Die entsprechende PostgreSQL-Klasse benutzt die vorhandene streng begrenzte
Provisionierungsfixture mit zufälligen eigenen Testfirmen, echten getrennten
Owner-/Runtimerollen und Datenbanken. Sie kontrolliert vor und nach jeder Kette
die tatsächlich verwendeten Rollen, Datenbank und feste Instanzidentität sowie
die tatsächlich verweigerte fremde Datenbankverbindung. Nach exklusiver Freigabe
des Testclusters bestanden **4/4**, einschließlich des echten Parserfalls,
in 22,865 Sekunden. Der anschließende reine Cleanupnachweis ergab null zusätzliche
Datenbanken, null `sp_test`-Rollen und null andere Verbindungen zu `smartplan_check`.
Der Cluster ist wieder freigegeben.

Ein vorab unabhängig gefundener Fehler der vorbereiteten PG-Testfixture ist
ausdrücklich getrennt dokumentiert: Der ganze Fixture-Datensatz enthielt eine
nicht serialisierbare lokale `binder`-Funktion und konnte nicht an einen mit
`spawn` gestarteten Worker übergeben werden. Jetzt erhält der Worker nur seine
explizite feste Konfiguration; API-Tokens/Archive und die Closure gehören nicht
dazu. Dies war ein statischer Fixturebefund, kein nachträglich behaupteter
PostgreSQL-Produktrotlauf. Die tatsächlichen korrigierten PG-Fälle sind oben belegt.

## Bisherige Regressionen und offene Schritte

- **58 bestehende Tests:** 55 bestanden, drei PostgreSQL-Fälle ohne reservierten
  DSN ausdrücklich übersprungen; 21,394 Sekunden. Enthalten sind die vorhandenen
  Instanz-, Provisionierungs-, unabhängigen Hostguard-, Export-, Events- und
  Importworkerregressionen. Die drei Skips sind keine bestandenen Nachweise.
- **1/1 tatsächliche UID-Prüfung**, 5,067 Sekunden: separate Linux-UIDs 24001/24002
  im Wegwerfcontainer können fremde private Dateien weder lesen, schreiben,
  löschen noch deren Elternverzeichnis umbenennen. Keine Hostkonten, Hostmounts,
  Netzverbindung oder persistenten Volumes wurden angelegt.
- **1 CI-Konfigurationsgegenfall:** vorher rot, nach enger Korrektur grün.
- Ein unabhängiger Review ergänzt Such-/Assistenten-/Sprachkontexte und
  Clientkontextwechsel. Seine bestätigten Produktbefunde und der aktuelle
  Nachlauf stehen oben; sein abschließender Hashhandoff ist noch aktiv.
- Der abschließende gemeinsame Hashhandoff folgt nach dieser Nativeprüfung.
  Anforderungen werden danach anhand des tatsächlichen Nachweises abgeglichen.

Ein umfassender produktiver Hoststart mit installierten Systemd-Units,
unterschiedlichen Dienst-UIDs, PostgreSQL-Peer-Anmeldung, DNS/TLS und
Wiederanlauf wurde hier noch nicht gemeinsam ausgeführt. Die einzeln belegten
Grenzen werden nicht als eine solche Hostabnahme ausgegeben. Eine unabhängige
externe Sicherheitsprüfung, produktive Bereitstellung und Betreiberverfahren
für Rotation/Upgrade bleiben gesondert. Bestätigte Fixes betreffen die
CI-Konfiguration und den nativen privaten Assistenten-/Sprachkontext beim
Wechsel einer Unternehmenssession. Keine neue Server-Mandantenarchitektur
wurde eingeführt und keine bestehende Datenbankgrenze gelockert.
