# Verbindlicher Arbeitsstand für die Fortsetzung

Stand: 09.11.2026. Projekt: `/workspace/Smarplan-Hofmann-Workspace`.
Lokaler Entwicklungsbranch: `codex/finish-20261108`.
Autorisierter Veröffentlichungsbranch: `codex/testupdate-0.7-projects-20261104`.

Letzter vollständig grün geprüfter Produktcode:
`eef1927b3e357344ad5713bed2633cfe65f813ce`, gemeinsamer Prüfstand
`ef1259c2e46e75a8c6befddf91de5a92861dee63`. Alle acht Development-Jobs
und der unsignierte iPhone-Build bestehen; der signierte Upload ist übersprungen.
Die ausdrücklich manuell gestarteten Prüfungen:
[Development42613341609](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42613341609),
[iPhone42613388458](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42613388458).
[Aktueller CI-Nachweis](evidence/completion-followup-2026-11-09/ci-after.json),
[Veröffentlichungsnachweis](evidence/completion-followup-2026-11-09/publication.json).
Der frühere vollständig grüne Stand 2598c96 und die älteren fehlgeschlagenen
Läufe bleiben in ihren historischen Nachweisen erhalten. Die zusätzlichen Änderungen sind anschließend als 4b8ec08/894ecdd veröffentlicht.
Die neue eigene Prüfung auf 894ecdd ist beendet: sieben Development-Jobs bestehen; der Browserjob scheitert am mobilen Sichtbarkeitskriterium der Anmeldung. Der iPhone-Prüflauf scheitert an einer festen Warteannahme beim echten Dateischreiben. Beide Fehler sind lokal korrigiert und gezielt nachgeprüft; die neue Remoteprüfung steht noch aus: [Development42624525741](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42624525741),
[iPhone42624525589](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42624525589).
[Veröffentlichungsnachweis](evidence/oneoff-provenance-2026-11-09/publication.json).
Der signierte Upload ist nicht angefordert.

Der Vorgänger 3025747 besteht nach erfolgreicher Simulatorwiederholung sieben
Development-Jobs und den unsignierten iPhone-Build. Sein vollständiger Browserjob
scheitert am späteren Lesen einer Antwort nach Seitenwechsel im Profiltest.
Die Korrektur ist im neuen veröffentlichten Stand enthalten und gezielt echt
nachgeprüft. Die erste Simulatorursache bleibt mangels abrufbarem ursprünglichem
Log unbestätigt. [Befund und Wiederholung](evidence/completion-followup-2026-11-09/ci-macos-retry.json).
Eine neue Serverinstallation oder Geräteabnahme ist nicht erfolgt.

## Ziel und fachlicher Umfang

Der Nutzer beauftragt am 08.11. erneut die Fertigstellung der gesamten Software
und fragt ausdrücklich nach dem Erhalt des Gesamtziels. Die ursprüngliche
[Gesamtzieldatei](../CRM_ERP_Gesamtziel.txt) ist vollständig erneut gelesen und
unverändert vorhanden: 23.863 Bytes, SHA-256
`a4dea28f6de4afd3e36d1549441aad91ce16dad374f56097979cc2d79b07fbf5`.

Endziel ist die zusammenhängende branchenübergreifende deutsche CRM-/ERP-Lösung
mit Kunden/Vertrieb/Portal, Projekten, Planung, Angeboten/Aufträgen/Rechnungen,
Material/Einkauf/Service/Betriebsmitteln, Zeiten und Dokumentation, eigener
Buchhaltung, deutscher Lohnabrechnung, Assistent/Regeln, geschützter Offlinearbeit,
Windows-/iPhone-/Browseranwendung, Installation/Betrieb und Abnahmen A–G.
Die frühere Projektphase war eine Reihenfolgeentscheidung, keine Streichung
von Buchhaltung oder Lohn aus dem Endziel.

Festgelegt bleiben Einzelunternehmen/EÜR, Regelbesteuerung mit Ist-Versteuerung,
19 % Standard-USt, SKR04, Nettopreise sowie reguläre Beschäftigte und Minijobs.
Weitere Länder und unbesprochene branchenspezifische Spezialprodukte gehören
nicht automatisch zur ersten deutschen Version.

## Wiederhergestellte Quellen und bestätigter Betriebsstand

Die neue Cloud-Umgebung startete mit dem alten sauberen Branch work auf
822fe58. Der neuere komplette Entwicklungsstand war dort noch nicht abgerufen.
Der autorisierte Remote-Testbranch wurde geholt und der letzte Stand 7c06f36
unter dem neuen lokalen Branch wiederhergestellt. Der alte Branch und die
vorhandenen Arbeitskopien bleiben erhalten. Die Wiederherstellung ist keine
neue Entwicklung und keine Serverinstallation.

Der letzte tatsächlich durch den Nutzer bestätigte Serverstand bleibt
`a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5`: Updateabschluss, drei Dienste,
Sandbox-/Datenbankbindung und aktiver Sicherungstimer bestätigt. Für das spätere
Browserupdate auf 5880f88 wurde ein Befehl bereitgestellt; sein Ergebnis ist
noch nicht vom Nutzer bestätigt. Eine Statusfrage ist gestellt. Der rein lesende Cloudabruf vom 09.11.
erreicht den Server wegen HTTP403 am Cloudproxy-CONNECT nicht; das ist kein
nachgewiesener Anwendungsfehler und bestätigt keine neuere Serverrevision.

Windows 0.13.0 und der unsignierte iPhone-Prüfbuild sind tatsächlich gebaut.
Der Remote-Lauf auf 5880f88 besteht Windows, Simulator, Flutter, Backend,
Online-API, Update und HTTPS. Der Business-/Browserjob scheitert im Assistenten-
Test an der Annahme eines nach Übersicht weiterhin ausgewählten Projekts.
Der iPhone-Prüfbuild besteht; der signierte Upload bleibt übersprungen.

## Aktuelle Integration am 09.11.2026

Hauptprojekt: `/workspace/Smarplan-Hofmann-Workspace` auf dem lokalen Branch
`codex/finish-20261108`. Der weitere Integrationskandidat steht in
`/workspace/smartplan-minijob-integration-20261109`; ältere vollständige
Arbeitskopien und Zwischenstände bleiben erhalten.
Der lokale gemeinsame Stand enthält die abgeschlossenen Projektmeilensteine,
die Korrekturen der drei nachgewiesenen CI-Testfehler und den neuen
[Wartungsvertragseditor](CRM_ERP_WARTUNGSVERTRAEGE_BROWSER_2026.md).
Dessen echter Browsernachlauf besteht auch auf dem gemeinsamen Backend;
alle 938 Browsermodultests bestehen.

Die bestätigte Offline-Firmenverwechslung wird mit einem ausdrücklich an
Instanz und Konto gebundenen V2-Vertrag geschlossen. Backend und reine
Hashprüfung stehen; 93 betroffene Speicher-/HTTP-/TCP-/TLS-Fälle und fünf
tatsächliche PostgreSQL-Migrations-/Konkurrenz-/Restorefälle bestehen. Die
native Umstellung ist mit 186 gemeinsamen und zwei ergänzenden tatsächlichen
HTTP-Fällen abgeschlossen; die Analyse ist ohne Befund. Die vollständige
Appprüfung des kombinierten Stands folgt.
V1-Dateien werden erhalten und keiner neuen Firma automatisch zugeordnet.
Die bestehenden gebundenen Lohn- und Portaltests verwenden nun echte
V2-Zugänge; elf zusätzliche HTTP-/Portal- und drei tatsächliche Lohn-/PG-/
Restorefälle bestehen. Die Berechtigungsgrenzen werden nicht gelockert.

Eine weitere echte HTTP-Reproduktion bestätigt doppelte manuelle Servicefälle
nach angenommener Anfrage, verlorener Antwort und vollständigem App-Neustart.
Der verschlüsselte, firmen- und kontogebundene Anlageauftrag ist integriert.
24 gezielte sowie 45 bestehende Service-/Editor-Fälle bestehen, einschließlich
tatsächlicher App-Neuerstellung und 390px-UI. Die gemeinsame vollständige
Appprüfung wird unten getrennt ausgewiesen.

Beim Lohn ist der eng begrenzte reguläre Faktor-Vollmonat mit ausschließlich
steuerfreien, tatsächlich bereits erstatteten Reisebelegen als neuer
Source3-Vertrag in Backend und beiden Clients integriert. Basislohn und
bestehende Rechenkerne bleiben unverändert; die Zahlung wird nicht nochmals
zum Netto addiert. Vier unabhängige PostgreSQL-Szenarien, tatsächlicher
Dump/Restore, ursprüngliche CRLF-Belege, der echte Browserablauf und 945
Browsermodulfälle bestehen. Der individuell besteuerte Minijob ist der
anschließende enge neue Backendvertrag. Eine zusätzliche
[Primärquellenprüfung](CRM_ERP_MINIJOB_PAP_MERKMALE_AUDIT_2026.md) belegt jetzt
die zuvor fehlende technische PKV-Zuordnung anhand des BMF-Schreibens für 2026
und reproduziert zwei passende Steuerwerte unabhängig mit der gepinnten XML.
36 unabhängige XML-Vektoren, private Originale, Lohnkonto, Jahresprojektion
und vier tatsächliche PostgreSQL-/Restore-/Konkurrenzfälle sind für diesen
Backendvertrag geprüft. Die tatsächliche Krankenversicherung wird dabei
nicht als privat umgeschrieben. Browser und App sind integriert: ausdrückliche
Nachweise, Identität V2, beide Rentenversicherungsfälle, unveränderte Wiederholung,
belegte Umstellung ungenutzter alter Fälle und ursprüngliche Dokumente.
Die unabhängige Prüfung fand zusätzlich einen zu schwachen Altbelegabgleich;
dieser ist vor Integration behoben. Sechs echte PostgreSQL-/MFA-/HTTP-/Restore-
Fälle, drei weitere Grenzfälle und ein tatsächlicher CRLF-/LF-Originalabgleich
bestehen. Bestehende Versionen und ihre Originale bleiben erhalten.
[V11-Clients](CRM_ERP_MINIJOB_V11_CLIENTS_2026.md),
[unabhängige Prüfung](CRM_ERP_MINIJOB_V11_UNABHAENGIGE_PRUEFUNG_2026.md).

Die konkret nachgewiesene Browserlücke ist geschlossen: Der Belegdialog kann
freigegebene abrechenbare Projektzeiten übernehmen, bestehende freie und
Katalogpositionen erhalten und auf den ursprünglichen Auftrag erneut zugreifen.
Der PostgreSQL-Ablauf bis zur ausgestellten Rechnung und PDF besteht, ebenso
Rechteentzug, überholte Auswahl, verlorene Antwort und Doppelabrechnungsschutz.
Drei PostgreSQL-Summen werden nun als ganze Sekunden zurückgegeben; dadurch
bleibt die bestehende kanonische JSON-/Hashdarstellung plattformgleich.
Ein zweiter echter PG-/MFA-/Chromiumlauf auf dem gemeinsamen Stand 487977a
bestätigt Rechnung, zwei Zeitbindungen, PDF-Hash und beide Integritätsprüfer.
[Browserzeitabrechnung](CRM_ERP_ZEITABRECHNUNG_BROWSER_2026.md),
[gemeinsamer Integrationsnachweis](CRM_ERP_ZEITABRECHNUNG_INTEGRATION_2026-11-09.md).

Der vollständige App-Lauf auf d4df2f5 ist beendet: 1.746 bestanden, vier
fehlgeschlagen, kein Skip, 38:31 Minuten. Drei Fehler stammen aus zwei
inkonsistenten gebundenen Testaufbauten; die Korrektur besteht separat mit
tatsächlichem HTTP und Temp-Pfadalias und ist im Kandidaten enthalten. Der
vierte Fehler war das fünfminütige Zeitlimit des Offene-Posten-Widgettests.
Sein künstlicher Zeitfortschritt und die Exportwartebedingung sind korrigiert;
der vollständige einzelne Fall besteht in 2:54 Minuten mit unverändertem
Gesamtzeitlimit und allen 38 bisherigen Assertions. Analyse ohne Befund.
[Nachweis](CRM_ERP_OPEN_ITEMS_WIDGET_WARTEZEIT_2026.md).
Der erneute vollständige App-Lauf auf 8273852 ist jetzt grün: 1.770 bestanden,
kein Fehler oder Skip, 22:03 Minuten laut Fortschrittslog. Die drei mit dem
echten nativen PDF-Renderer geprüften Fälle bestehen getrennt. Das vollständige
Maschinenprotokoll ist ebenfalls erhalten. Auf dem gemeinsamen Stand 487977a bestehen 972
Browsermodulfälle und 48 gezielte native Fälle. Rohprotokolle einschließlich
der Fehlversuche liegen unter
[final-assembly-2026-11-09](evidence/final-assembly-2026-11-09/checks-so-far.json).
Alle 32 historischen Rechenmodule, die ursprüngliche V1-Zahlungsarithmetik
und die Gesamtzieldatei sind erneut bytegleich geprüft.

Der gemeinsame Stand 82738522d132918b0f139011302e5862f40c1e92 ist am 09.11.
ohne erzwungenes Überschreiben auf dem autorisierten Testbranch veröffentlicht.
Seine neuen Prüfungen laufen:
[Development42654230472](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42654230472),
[iPhone42654230385](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42654230385).
Fünf Development-Jobs bestehen: Backend, Update, HTTPS, Flutter und Mac-Simulator.
Online-API scheitert an einem veralteten V1-Zugangsaufbau in einer gebundenen
Testfirma. Windows scheitert am Import einer POSIX-Serverprovisionierung im
eingebetteten Testserver. Beide Testursachen sind separat korrigiert; 52
betroffene Buchhaltungs-/Berechtigungsfälle, beide tatsächlichen nativen HTTP-
Fälle und die portable Testauswahl bestehen. Die Windows-Auswahl ist lokal
auf Linux geprüft; eine tatsächliche neue Windows-CI wird damit nicht ersetzt.
[Testkorrektur und ursprüngliche Fehlprotokolle](CRM_ERP_CI_OFFLINE_FIXTURES_2026-11-09.md).
Business-/Browserjob sowie der unsignierte iPhone-Build sind noch aktiv.
Die vollständige lokale Appprüfung auf genau diesem Stand ist inzwischen grün.
Der signierte Upload ist nicht angefordert.
[Veröffentlichungsnachweis](evidence/final-assembly-2026-11-09/publication.json).
[Zwischenstand der tatsächlichen CI-Ergebnisse](evidence/final-assembly-2026-11-09/ci-827-intermediate.json).
Der vorherige 3859a1c bleibt mit sechs Erfolgen und zwei Fehlern dokumentiert.
Der letzte vollständig grüne Produktstand bleibt bis zum neuen Ergebnis eef1927.
Keine neuere Serverinstallation oder echte Geräteabnahme ist bestätigt.

## Nachweise vorangegangener Abschnitte bis 3859a1c

Die positive Korrektur eines bezahlten einzelnen Source5-Bonus ist gemeinsam
integriert in `/workspace/smartplan-source5-integration-20261109`, Branch
`codex/source5-positive-integration-20261109`. Backend, Browser und native App
verwenden denselben neuen Übergangs-/Zahlungsvertrag. Der alte v1-Vertrag und
alle 32 historischen 2026-Rechenmodule bleiben bytegleich zur Basis af98278.

Unverändertes Brutto-/Zuflussereignis und laufende Rechnung, belegter vollständiger
Zahlungspräfix, positive zusätzliche Nettoteile am ursprünglichen Tag und
komponentenweise Abführungsgrenzen sind verbindlich. Ein privates Original
belegt die ausdrücklich bestätigte Vollständigkeit aller Zahlungen/Abführungen;
leere Cashlisten allein reichen nicht. Zwei aufeinanderfolgende Nachzahlungen
und eine unbezahlte Zwischenrevision werden getrennt geprüft.

Vier echte PostgreSQL-/MFA-/HTTP-/Konkurrenz-/Restorefälle bestehen. Der zusätzliche
finale Jahres-/Mitarbeiter-/Restorefall besteht ebenfalls. 902 Browsermodul-,
23 ausgewählte native und 16 Paketfälle bestehen; Appanalyse ohne Befund.
Zwei echte Browserdurchläufe des neuen Falls mit verlorenen Antworten bestehen.
Der neue vollständige Lohn-/Reisesammellauf besteht mit 713 unterschiedlichen Fällen ohne Skip in 1519,359 Sekunden.
[Vertrag](CRM_ERP_SOURCE5_POSITIVE_KORREKTUR_2026.md).

Der neue Abschnitt ist noch nicht veröffentlicht. Vor der Veröffentlichung
sind die unabhängig auf 894ecdd gefundenen mobilen Anmelde- und nativen
Dateispeicher-Testfehler korrigiert; echte mobile Anmeldung und 66 native
Datei-/Originalfälle bestehen. Der letzte vollständig grüne gemeinsame
Remote-Prüfstand bleibt ef1259c. Bereits gezahlte negative Korrekturen,
spätere tatsächliche Zahlungstage und mehrere Bonus-Steuergruppen bleiben
separate Code-/Fachaufgaben; [konkreter Gruppenplan](CRM_ERP_SOURCE5_MEHRFACH_GRUPPEN_RESTPLAN_2026.md).

Außerhalb der Lohnrechnung sind die [vollständigen Browser-Projektaufgaben](CRM_ERP_PROJEKTAUFGABEN_BROWSER_2026.md) bereits integriert und getrennt geprüft.
Die [über Neustart haltbare unbestätigte Projektanlage](CRM_ERP_PROJEKTANLAGE_NEUSTART_2026.md) ist ebenfalls integriert.
Der [gemeinsame Liefernachweis](CRM_ERP_PROJEKT_LIEFERSTAND_2026-11-09.md) hält
183 native, 45 Backend-, vier tatsächliche PG-/Konkurrenz-/Restore-,
912 Browsermodul- und 16 Paketfälle sowie den echten Browsernachlauf fest.
Der gemeinsame Stand 3859a1c ist veröffentlicht. Development42634757414 und iPhone42634757313 laufen; der signierte Upload ist nicht angefordert. explizite
Projektmeilensteine werden bereits getrennt entwickelt.

Der [Einmalbezugs-Abgleich](CRM_ERP_LOHN_EINMALBEZUG_PLATTFORMHISTORIE_2026.md)
ist aus der eigenen Arbeitskopie als 894ecdd in den Hauptstand übernommen.
Der Quellbranch `codex/oneoff-provenance-20261109` mit e632991 und seine
Arbeitskopie bleiben erhalten. Exakter Prüfer für acht v6/v7-Metadatenvarianten;
Case-/Run-Adapter und privater Source5-Zahlungsresolver erhalten Original- und
abhängige Bindungshashes. Sieben neue Fachkettenfälle, vier tatsächliche
PG-/MFA-/Konkurrenz-/Restorefälle, tatsächlicher Vergleich mit dem alten Windows-
Paket, 884 Browsermodule, 31 ausgewählte App- und 16 Paketprüfungen bestehen;
App-Analyse ohne Befund. Die 32 historischen Rechenmodule und die alte v1-
Zahlungsarithmetik sind bytegleich. Im Sammellauf von 694 verschiedenen Lohn-/Reisefällen bestehen 683; elf lokale
HTTP-Listener scheitern ausschließlich mit Socket-EPERM. Genau diese elf
bestehen nach Freigabe in 24,294 Sekunden. Erfolgreich geprüfte unterschiedliche Fälle: 694, keine
Skips; der erste Sammellauf bleibt mit Exit 1 und 1115,245 Sekunden erhalten.
Ein einzelner vollständig grüner Sammellauf wird nicht behauptet. Die gemeinsam
integrierten Übersichts-/Original-/Zahlungs-/EÜR-Wege bestehen zusätzlich fünf
Fälle in 21,932 Sekunden. Der Produktcode ist als 894ecdd veröffentlicht; seine neue Remote-CI läuft.

Abgeschlossener Browser-Nachlauf: Die erste vollständige lokale Wiederholung kommt
über den früheren Profilfehler hinaus und prüft Einkauf/Kalender, läuft dann
aber in die Anmeldeannahme auf die nachgeladene Übersichtsüberschrift.
Der Anmeldehelfer prüft jetzt den tatsächlichen Abmeldeknopf und die exakt
vom Server gelesene Identität. Der gezielte echte Profil-/Kalender-/Recovery-
Fall besteht. Die zweite vollständige Folge macht den wirklichen weiteren
Engpass sichtbar: `/business/overview/metrics` hält nach vielen dokumentierten
Geldflüssen länger als 15 Sekunden die Transaktion; auch die nach Navigation
frisch angefragten Metadaten warten. Screenshot und offene Pfade sind erhalten.

Die zusätzliche Produktkorrektur teilt die vollständig validierte C2/R2-Rekonstruktion
nur innerhalb eines serialisierten EÜR-Aufrufs. Keine Historie, Rechenregel,
Frist oder Berechtigung wird vereinfacht; der Cache wird auch bei Fehlern
entfernt und nie zwischen Aufrufen behalten. Drei neue Regressionen und alle
26 bestehenden EÜR-/Übersichts-/HTTP-Fälle bestehen in 42,233 Sekunden ohne
Skip. Die Vergleichsrechnung ohne Wiederverwendung liefert exakt dieselben
Berichte, Quellen, Beträge und Hashes. Änderungen an Originalen, neue Geldflüsse
und Rechteentzug bleiben frisch geprüft. Alle 17 vollständigen Browserabläufe bestehen jetzt, einschließlich erneuter
MFA-Anmeldung, Kalender und mobiler Folge. Auch die vier bestehenden tatsächlichen
EÜR-PG-/Restorefälle bestehen ohne Skip in 93,676 Sekunden. Die Vergleichskopie
des vorher fehlgeschlagenen Teststands liefert identische Inhalte in 1,863
statt 18,406 Sekunden; dies ist keine zugesicherte Produktionslaufzeit.
[Änderung und Nachweise](CRM_ERP_UEBERSICHT_LESEKETTE_2026.md).
Diese neuen Änderungen sind als 4b8ec08/894ecdd veröffentlicht; die neue Remote-CI läuft. Keine neue Serverinstallation.

Neu integriert und veröffentlicht: [alte Reiseoriginale zwischen Windows/Linux erhalten](CRM_ERP_REISEN_PLATTFORMHISTORIE_2026.md).
Die v2/v3-Transportnachweise und v3-Boden-/Programmquellen werden mit exakt
hergeleiteten LF-/CRLF-Metadaten nachgerechnet, während alle Originale und
Finanzdaten erhalten bleiben. Sieben neue Fachkettenfälle, drei tatsächliche
PG-/MFA-/Konkurrenz-/Restorefälle, EÜR/Bankabgleich, beide Browserabläufe und
881 Browsermodule, 24 native Reiseprüfungen und alle 687 unterschiedlichen
Python-Lohn-/Reisefälle bestehen ohne Skip. App-Analyse ohne Befund. Die alte
tatsächliche Windows-Paketberechnung stimmt unabhängig mit dem Original
überein. Die eigene Remote-CI läuft. Die zuvor abgebrochene vollständige
lokale Browserfolge wird zusätzlich nachgeprüft.


Der [belegte Faktor-Teilmonat](CRM_ERP_LOHN_FAKTOR_TEILMONATE_2026.md) ist als
additive v9-Regel mit Quelle2 in Backend, Browser und nativer App integriert.
200 unabhängige PAP-XML-Vektoren stimmen überein. Original/Korrektur,
Mitarbeiterbeleg, Zahlung/EÜR, drei neue tatsächliche PG-/MFA-/Restore-/Bankfälle
und die drei bisherigen Perioden-PG-Fälle bestehen. 313 native Lohnfälle,
879 Browsermodule, beide tatsächlichen Perioden-Browserwege und 16 Paketfälle
bestehen; App-Analyse ohne Befund. Alle 644 unterschiedlichen Python-Lohnfälle
bestehen ohne Skip. Die Erweiterung ist über 877266a und den Folgefix 3025747
veröffentlicht; die neue Remote-Prüfung besteht sieben Jobs, während der
oben beschriebene Browser-Testfehler im Nachfolger korrigiert wird.

Die historischen Kernmodule bleiben bytegleich. Neue v9-Quellmetadaten verwenden
LF-normalisierte Dateihashes. Der Vergleich mit 146 verifizierten Quellen aus
einem tatsächlichen Windows-Paket bestätigt dasselbe vollständige v9-Ergebnis.
Er zeigt zugleich eine reale Restlücke: alte v8-Quellmetadaten unterscheiden
sich bei Windows-/Linux-Zeilenenden. Der neue [historische v8-Abgleich](CRM_ERP_LOHN_PLATTFORMHISTORIE_2026.md)
prüft exakt hergeleitete Metadatenpaare bei sonst vollständiger Gleichheit.
Fünf neue Fachkettenfälle, zwei tatsächliche PG-/MFA-/Neustart-/Restorefälle
und der Vergleich mit den veröffentlichten Windowsquellen bestehen. Originale,
Geldbeträge, PDF- und Quellhashes bleiben erhalten. Alle 649 unterschiedlichen
Python-Lohnfälle bestehen ohne Skip. Der Folgeabschnitt ist als 3025747
veröffentlicht. Der zusätzliche Reiseabgleich ist oben beschrieben. Der
zusätzliche Einmalbezugsabgleich ist oben beschrieben.

1. **Wiederherstellung/Originalziel:** abgeschlossen und per Hash geprüft.
2. **Browserregressionen:** Assistent, Zusatzfelder und Kundenbereich verwenden
   nach allgemeinen Seiten wieder eine ausdrückliche Projektwahl. Der Assistent
   wählt zudem seine erlaubte Datenbasis erneut, bevor er gezielt Artikel sucht.
   Die neue Navigation wird damit nicht auf ihre frühere globale Wirkung
   zurückgestellt.
3. **Parser-Kompatibilität vor Updates:** Der neue Quellstand prüft einen bereits
   installierten Parser mit künftigem Backendcode, tatsächlicher Dienst-UID,
   NoNewPrivileges, leerer vertraulicher Umgebung und vollständigem Sandboxbericht.
   Fehler liegen vor Wartung, Dienststopp, Journal und Kandidatenvorbereitung.
   Es findet keine automatische Paketänderung statt. Die spätere tatsächliche
   systemd-Startprüfung bleibt zusätzlich bestehen.
4. **Nachweis:** 87 Update-/Recovery-/Operatorfälle, 21 Import-API-Fälle, 860
   Browser-Modultests und gezielte echte MFA-/HTTP-/Chromium-Abläufe bestanden.
   [Aktueller Prüfnachweis](evidence/project-resume-2026-11-08/verification.json).
5. **Steuerklasse IV mit Faktor:** Der begrenzte reguläre Vollmonat ist mit
   neuer Regel v8 in Backend, Browser und nativer App integriert. Belegte
   Merkmale, Vorschau, Korrektur, Originalwiederholung, private und reduzierte
   Belege, Jahresübersicht sowie tatsächliche Zahlungen/EÜR sind geprüft.
   170 unabhängige XML-Vektoren, 631 unterschiedliche Python-Lohnfälle über
   Gesamt-/Socketnachlauf und zusätzlichen EÜR-Fall, sechs reale PG-/Restorefälle,
   306 App-, 866 Node- und 16 Paketfälle sowie echte Faktor-/Midijob-Browserwege
   belegen den abgegrenzten Umfang. [Quellen, Grenzen und Nachweis](CRM_ERP_LOHN_FAKTOR_2026.md).
6. **Gemeinsame Kunden-/Projektkommunikation:** neuer reiner Leseverlauf aus
   sechs bestehenden Fachquellen in Browser und nativer App. Suche, Quelle,
   Datum, Snapshotseiten und Original/Korrektur erhalten native Quellrechte.
   Tatsächliche MFA-/Browser-/PostgreSQL-/Restoreprüfungen bestanden; alle
   22 nativen Projektregister sind in Desktop-/Mobilbreite nachgeprüft.
   Der zusätzliche vollständige lokale App-Lauf auf b57f474 besteht 1.632
   Fälle ohne die gesonderten nativen PDFfälle. Der abschließende Browserstand
   besteht 874 Modulfälle und echte verspätete Kunden-/Filterantworten.
   [Umfang und Grenzen](CRM_ERP_KOMMUNIKATIONSVERLAUF.md).
7. **Windows-Artefakt:** Onlinepaket auf f747311 tatsächlich heruntergeladen;
   veröffentlichter Archivdigest und alle 248 Dateihashes stimmen. Es ist
   damit noch nicht auf einem echten Windowsgerät bedient oder installiert.

## Laufender nächster Abschnitt: Projektmeilensteine

Die getrennten Arbeitskopien auf Basis 6a454ca sind:

- Backend: `/workspace/smartplan-project-milestones-backend-20261109`,
  `codex/project-milestones-backend-20261109`.
- Browser: `/workspace/smartplan-milestones-browser-20261109`,
  `codex/project-milestones-browser-20261109`.
- Native App: `/workspace/smartplan-milestones-native-20261109`,
  `codex/project-milestones-native-20261109`.
- Gemeinsame Vorbereitung: `/workspace/smartplan-milestones-integration-20261109`,
  `codex/milestones-integration-20261109`, Basis veröffentlichter Lieferstand.

Vereinbart ist ein eigener versionierter Baustein mit Titel, Beschreibung,
optionalem Termin und Verantwortlichem sowie manuellem Status
`planned`, `achieved` oder `cancelled`. Eigene unveränderte Historie und
Auftragsquittungen, frische Projekt-/Planungsrechte und unveränderte bestehende
Aufgaben/Termine gehören zum Umfang. Ein erreichter Meilenstein ist keine
rechtliche Abnahme und erzeugt keine automatische Rechnung oder Zahlung.
Backend/Browser/App und aktuelle Fixtures sind zusammengeführt. [Gemeinsamer Nachweis](CRM_ERP_PROJEKTMEILENSTEINE_GESAMTPRUEFUNG_2026-11-09.md): 130 native, 927 Browsermodul-, 23 Backend-, zwei tatsächliche PG-/Restore- und 16 Paketfälle bestehen. Der separate echte Browsernachlauf besteht ebenfalls. Veröffentlichung und neue Remoteprüfung stehen noch aus.

## Unmittelbar folgende Isolationskorrektur

Ein tatsächlicher synthetischer Client-/Servernachweis auf 60f9001 bestätigt
am 09.11.2026 einen Fehler des bisherigen Offline-Caches: Bei gleicher
Serveradresse, Benutzer- und Projektkennung kann eine neue Anmeldung an
Unternehmensinstanz B alte verschlüsselte Planaufträge aus A mit dem neuen
B-Token synchronisieren. Das alte A-Token wird von B korrekt abgewiesen;
der Fehler ist die fehlende Instanzbindung bei Wiederanmeldung im Client.
Dies ist eine konkrete offene R03.04-Korrektur, keine Produktivfreigabe.

[Unveränderte Reproduktion](evidence/offline-company-isolation-2026-11-09/initial-reproduction.json).
Ein additiver Grant-/Cachevertrag und sichere Behandlung vorhandener noch
nicht gebundener Offlineaufträge werden vorbereitet. Vorhandene Dateien und
Aufträge dürfen nicht gelöscht oder ungeprüft einer neuen Instanz zugewiesen
werden. Der Fix wird mit eigenem Nachweis entwickelt; die Meilensteinintegration ist lokal abgeschlossen. Neue V2-Grants und getrennte Cache-/Token-Namensräume binden Instanz und Konto. V1-Bestände ohne nachweisbare Herkunft bleiben erhalten und gesperrt; sie werden keiner neuen Firma automatisch zugewiesen.

## Laufende Offline-V2-Integration

Der gemeinsame, noch unveröffentlichte Stand liegt in
`/workspace/smartplan-offline-instance-integration-20261109`, Branch
`codex/offline-instance-integration-20261109`. Er enthält Meilensteine und die
neue serverseitige Firmenbindung. Der Backendquellzweig liegt unter
`/workspace/smartplan-offline-instance-backend-20261109`, die native Arbeit unter
`/workspace/smartplan-offline-instance-native-20261109`.

Ein zusätzlicher tatsächlicher PostgreSQL-Nachweis besteht mit zwei Fällen
nach Korrektur des neuen Triggerfunktionsnamens auf die bereits zugelassene
`business_`-Namenskonvention. Die vorhandene Ownership-Prüfung wurde nicht
geweitet. Migration erhält V1-Daten; V1-Gerätezugriffe sind in gebundenen
Instanzen gesperrt; Restore widerruft V2-Gerätezugänge und erhält Planoriginale.
Dieser Lauf betrifft den serverseitigen Zwischenstand. Native Umstellung und
der neue ausschließlich hashbasierte Altauftragsabgleich sind noch in Arbeit.
Ein alter Planinhalt darf zur Herkunftsprüfung nicht an die möglicherweise
falsche neue Firma übertragen werden. Negative Abgleiche geben keine Sendung frei.

Der erste Fehlversuch und erfolgreiche Nachlauf stehen unter
`docs/evidence/offline-binding-integration-2026-11-09/`. Der dafür angelegte
eigene Testcontainer ist nach dem abschließenden PostgreSQL-Hash-only-Nachlauf
(2/2 bestanden) entfernt; er verwendete nur synthetische Daten. Die früheren Meilenstein- und Projektjournalcontainer sind
bereits entfernt.

## Weitere unabhängige Entwicklungsarbeit

- Korrigierten Browser-Gesamtlauf und neue eigene Remote-CI abschließen.
  ef1259c mit Produktcode eef1927 bleibt der letzte vollständig grüne Prüfstand.
- Historische plattformabhängige Lohn-/Reisemetadaten vollständig abgleichen.
  Der v8-Faktor-Vollmonat und die v2/v3-Reisekosten sind eng begrenzt geprüft;
  der entsprechende v6/v7-Einmalbezugsabgleich ist inzwischen ebenfalls integriert.
- Weitere benannte Standard-Lohnfälle additiv integrieren. Dazu gehören unter
  anderem Faktor-Ansprüche/-Einmalbezüge und Midijobs mit Faktor, individuelle Minijobsteuer, Versicherungsvarianten,
  Minijob-Jahresgrenzen und weitere Leistungen/Sachbezüge. Der
  [Lohn-Lückenplan](CRM_ERP_LOHN_LUECKENPLAN_2026.md) bewahrt auch historische
  Ausgangspunkte; pro Fall den heutigen Code prüfen. Bestehende begrenzte
  Berechnungen bleiben unter ihren gespeicherten Versionen reproduzierbar.
- EÜR-/Abschlussfälle, Auswertungen, Länder-/Regeltrennung und erlaubte
  Unternehmensaktionen gemäß der Anforderungsmatrix weiter vervollständigen.
  Fehlender Code wird nicht als externer Freigabemangel bezeichnet.
- Abnahmen A–G zu einem durchgängigen Lieferumfang verbinden. Lokale Fixtures
  ersetzen keine tatsächliche Windows-/iPhone-Bedienung oder Liveintegration.

Der neue Faktor-Vollmonat verlangt einen tatsächlich belegten Faktor und
erhält alle historischen PAP-Dateien bytegleich. Seine geprüfte Implementierung
ist keine vollständige Lohnfreigabe. Weitere Versicherungs-, Minijob- und
Faktor-Spezialfälle bleiben eigenständige Codearbeit; der Lückenplan wird
dementsprechend fortgeschrieben.

## Tatsächliche externe Voraussetzungen

Für signierte iPhone-Verteilung ist die Verfügbarkeit eines Apple-Developer-
Kontos angefragt. Schlüssel gehören in die vorgesehenen geschützten Einstellungen,
nicht in den Chat. Anbieter/Originalformate und reale Zugänge werden bei den
konkret ausgewählten Schnittstellen benötigt. Fachliche/rechtliche Abnahme,
unabhängiger Sicherheitstest und gegebenenfalls Meldezulassungen bleiben eigene
Nachweise. Diese Punkte stoppen keine davon unabhängige Codearbeit.

Die gesamte Software ist noch nicht als vollständig fertig oder produktiv
freigegeben ausgewiesen. Maßgeblich bleiben alle Anforderungen und Abnahmen
im Originalziel; es wird kein Fertigstellungsprozent aus Dateien oder Testzahlen
abgeleitet.
