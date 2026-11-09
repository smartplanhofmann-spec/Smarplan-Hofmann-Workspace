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

## Konkrete aktuelle Arbeit

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
