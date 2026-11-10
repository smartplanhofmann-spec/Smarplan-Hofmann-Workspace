# Verbindlicher Arbeitsstand für die Fortsetzung

Stand: 10.11.2026. Projekt: `/workspace/Smarplan-Hofmann-Workspace`.
Lokaler Entwicklungsbranch: `codex/finish-20261108`.
Autorisierter Veröffentlichungsbranch: `codex/testupdate-0.7-projects-20261104`.

**Aktive technische Gesamtprüfung:** Die bisherigen154 Online- und nun78
Browserabläufe werden vollständig auf je sechs unabhängige Gruppen verteilt.
Neun vorhandene Browserziele fehlten bislang in der zentralen CI und sind
zusätzlich aufgenommen. Sieben Auswahl-/Fehlerverträge,25 echte MFA-/HTTPfälle,
1041 Browsermodul- und21 Paket-/Inventarfälle bestehen; sechs komplette lokale
Browsergruppen laufen. [Vertrag, Rohfehler und Grenzen](CRM_ERP_GESAMTPRUEFUNG_GRUPPEN_2026-11-10.md).
Kein neuer Push oder Live-/Gerätestand; Gesamtauftrag bleibt aktiv.

**Aktueller geprüfter Codeabschnitt (10.11.):** Der lesende Abgleich alter
Offline-Serviceprotokolle ist als aa2ab36 auf799c144 integriert:1.915 vollständige
Appfälle ohne Fehler/Skip,58 gemeinsame Backend-,29 native Altbestands-, ein
echter nativer MFA-/TCP-/PDF-/Zweifirmenfall, drei neue plus sechs bestehende
PostgreSQL-/Restorefälle und21 Paketfälle bestehen. Analyse sauber8,3s.
[Umfang und offene Grenzen](CRM_ERP_ALTBERICHT_ABGLEICH_2026-11-10.md),
[27 rohe Prüfdateien](evidence/legacy-service-recovery-2026-11-10/manifest.json).
Keine Wiederübertragung alter Inhalte oder automatische Freigabe ungebundener
Altbestände. Dieser Abschnitt ist noch nicht veröffentlicht; Testbranch799c144
ist bestätigt, eigene CI hat im letzten Abruf sechs erfolgreiche und zwei
laufende Development-Jobs. Kein neuer Live-/Gerätestand. Die folgenden älteren
Momentaufnahmen bleiben als Verlauf erhalten.

**Unmittelbare Folgearbeit:** Vollständige automatische Gesamtprüfungen auf
unabhängige Gruppen verteilen und alle bisherigen Fälle nachweisbar erhalten;
anschließend die verbleibenden Code-/Gesamtabnahmepunkte weiter abarbeiten.
Der Gesamtauftrag endet ausdrücklich nicht mit diesem Teilabschluss.

**Aktueller Codeabschnitt:** Faktor-/Anspruchsvertrag V12 ist in beiden Clients
und Backend integriert. 55 Backend-,1041 Browser-, neun neue native und21
Paketfälle sowie echte PG-/MFA-/Konkurrenz-/EÜR-/Jahres-/CRLF-/Restoreprüfung
bestehen. Die korrigierte gesamte Appprüfung besteht mit1.905 Fällen ohne
Fehler oder Skip; erster fehlgeschlagener Lauf bleibt erhalten. [Stand und genaue Grenzen](CRM_ERP_FAKTOR_ANSPRUECHE_V12_2026-11-10.md).
Aktuell veröffentlichter Testbranch: cb7ff63199757da72959a8b52161b6eff62e0117
(echte Anmeldeantwort im Belegrestbetragsbrowser); eigene CI42758607318 läuft.
V12 noch nicht veröffentlicht; kein neuer Server-/Gerätestand.

**Gesamtauftrag am 10.11. ausdrücklich fortgesetzt:** Keine Einzeletappe beendet
 den Auftrag. Die verbleibende Codearbeit und technische Gesamtabnahme werden
 weiter abgearbeitet; echte externe Freigaben bleiben als solche benannt.

**Neue geprüfte Stabilitätskorrektur:** Der tatsächlich rote Browserjob129611954657
auf 936f40f ist durch einen isoliert reproduzierten Fehler gleichzeitiger
SQLite-Lese-Cursor eingegrenzt. [Korrektur und Nachweise](CRM_ERP_SQLITE_PARALLELLES_LESEN_2026-11-10.md):
keine Wiederverwendung vorbereiteter Abfragen der gemeinsamen lokalen Verbindung;
Schema- und Archivschutz bleiben aktiv. 77 gemeinsame Fälle und echter
Bestell-/Teil-/Restlieferungsbrowser bestehen. Noch nicht veröffentlicht;
Remoteprüfung und Gesamtziel laufen weiter. V5 ist auf diesem Stand zusammengeführt.

**Veröffentlichung vor dem V5-Folgestand (Momentaufnahme):** V3-Folgeketten und tatsächliche Rückzahlung V4
sind als `936f40f57c769dce515099b4fecc616d05b35280` auf dem autorisierten
Testbranch veröffentlicht; Remote-SHA bestätigt. Eigene Development42750261490 besitzt erfolgreiche Backend-, Windows-, Mac-, App-,
HTTPS- und Updatejobs, aber einen echten Fehler im Einkaufsbrowser.
Der Fehler ist als SQLite-Leserennen reproduziert und lokal18b7031 korrigiert.
Online-API läuft noch; iPhone42750261604 besteht unsigniert, signierter Upload
ist übersprungen.
17978f6 bleibt der letzte vollständig grüne Stand mit allen acht Development-
Jobs und unsigniertem iPhone-Build; signierter Upload übersprungen.
Keine neue Serverinstallation oder Geräteabnahme.

**Abgeschlossener Codeabschnitt:** [Tatsächliche Netto-Rückzahlung V4](CRM_ERP_SOURCE5_NETTORUECKZAHLUNG_V4_2026-11-10.md)
mit 50 Backend-, 1.026 Browser-, 1.878 vollständigen App- und 21 Paketfällen,
echtem Browser sowie PG/MFA/EÜR/Jahresbasis/Restore. Zusätzliche tatsächliche
Konkurrenz-/Sperrprüfung besteht nach gezielter 423-Korrektur; alte Fehler bleiben
in den [Rohnachweisen](evidence/source5-repayment-2026-11-10/manifest.json) erhalten.
V3-Folgeketten b437f2c sind enthalten; Code749a19d und Nachweise936f40f.

**Vorheriger Codeabschnitt:** [Weitere Nettoausgleiche V5](CRM_ERP_SOURCE5_NETTOAUSGLEICHE_V5_2026-11-10.md)
in `/workspace/smartplan-source5-adjustments-20261110`. Wiederholte positive,
negative und betragsgleiche Korrekturen nach einem vollständig belegten
V4-/V5-Präfix sind in Backend und beiden Clients integriert. Erste unveränderte
Reproduktion rot; jetzt 48 gemeinsame Backend-, 1.035 Node-, 1.896 vollständige
App- und 21 Paketfälle, neun neue App-Bedienfälle und echter MFA-/Browserablauf
bestehen. Analyse sauber10,2s. Der tatsächliche PG-/Restorenachlauf besteht
mit einem Fall/1.019,007s einschließlich EÜR, Jahresbasis und Original-PDF.
Die separat geprüfte SQLite-Korrektur18b7031 ist zusammengeführt; beide echten
Browser, drei gemeinsame SQLite-/V5-Fälle/88,686s und 21 Paketfälle/16,078s
bestehen anschließend. Die eigene Wegwerf-Datenbank ist entfernt. Die lokalen
technischen V5-Nachweise sind vollständig gesichert. Neue Veröffentlichung/CI
und fachliche Gesamtabnahme sind gesondert. Der nächste Codeabschnitt gemäß
Gesamtplan behandelt belegte Lohnansprüche im Faktorfall.
Ein abgeschlossener Abschnitt beendet ausdrücklich nicht den Gesamtauftrag.

Der frühere Zeitabgleich 75d88a3 ist veröffentlicht. Vier eigene Development-
Jobs bestehen; vier weitere sowie beide iPhone-Jobs sind beim Nachfolger
abgebrochen. Der damalige erste Abruf bleibt historisch erhalten und wird nicht
nachträglich als Gesamtprüfung ausgegeben.

**Neuer vollständig grüner Produktstand:** `ab632c0b680b563169ec9e846ab9b406762bcc97`
besteht inzwischen sämtliche acht eigenen Development-Jobs einschließlich
Windows und Mac-Simulator sowie den unsignierten iPhone-Releasebuild.
Der signierte Upload ist übersprungen. Der erste Abruf unten bleibt historisch;
[abgeschlossener tatsächlicher Abruf](evidence/offline-legacy-time-core-2026-11-09/previous-product-ci-completed.json).
Keine neue Serverinstallation oder echte Geräteabnahme ist damit erfolgt.

**Vorangegangene Veröffentlichung, ursprünglicher Abruf:** Die geprüfte native Einzelprüfung alter
Planaufträge ist als `ab632c0b680b563169ec9e846ab9b406762bcc97` auf dem
autorisierten Testbranch veröffentlicht; der Remote-Zeiger ist bestätigt.
[Development42713870349](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42713870349)
und [iPhone42713870363](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42713870363)
laufen. HTTPS und Update bestehen im ersten Abruf, die übrigen Jobs sind offen.
[Veröffentlichung und ursprünglicher Abruf](evidence/offline-legacy-recovery-native-2026-11-09/publication-initial.json).

43 gemeinsame Offline-/Navigations-/Originalfälle und die vollständige
Appanalyse bestehen. Die [neue Ansicht](CRM_ERP_OFFLINE_ALTBELEGE_NATIVE_2026-11-09.md)
verwendet den tatsächlichen historischen V1-Dateiaufbau, Geräteentsperrung und
frische Firmen-/Originalprüfung. Alte Dateien, Schlüssel, Token und Auswahl
bleiben erhalten. Ein Treffer bestätigt nur einen einzelnen alten Auftrag;
vollständige Migration und andere Altwarteschlangen bleiben Restarbeit.

Der vorangegangene Browser-/Reisestand
`03b7b6df8215fa700b1ca94b4ef0bc588e079b4b` besitzt sechs erfolgreiche eigene
Development-Jobs, einschließlich Windows, Mac-Simulator und vollständiger
Appprüfung. Online-API und Business-Browser sowie beide iPhone-Jobs sind
beim Nachfolger abgebrochen; sie werden nicht als erfolgreich ausgegeben.
[Ursprünglicher erster Abruf](evidence/browser-original-restart-2026-11-09/publication-initial.json),
[späterer tatsächlicher Status](evidence/offline-legacy-recovery-native-2026-11-09/publication-initial.json).
Die [geschützte Browser-Wiederaufnahme](CRM_ERP_BROWSER_ORIGINALJOURNAL_VERTRAG_2026-11-09.md)
bleibt mit 1.017 Browsermodul-, 65 Backend-, 38 nativen und 16 Paketfällen
sowie beiden tatsächlichen Browser-/MFA-/IndexedDB-Neustartabläufen geprüft.
Die [Reisezeitpunktkorrektur](CRM_ERP_REISEZEITPUNKT_2026-11-09.md) besteht ihre
vier tatsächlichen PostgreSQL-/Restorefälle. Veröffentlichung/CI, laufender
Server und Geräteabnahme sind weiterhin getrennte Zustände.

**Vorangegangene Veröffentlichung:** Die native Wiederaufnahme ist als
`9271be79857e182adc080dcb8b1d86c48776dbdf` auf dem autorisierten Testbranch
veröffentlicht. Development42702226560 ist abgeschlossen: sechs erfolgreiche
Jobs, Fehler in Business-Browser und Online-API. Der eigene iPhone-Prüfbuild
42702226835 ist erfolgreich; der signierte Upload ist übersprungen.
[Ursprünglicher erster Abruf](evidence/native-journal-downgrade-2026-11-09/publication-initial.json),
[späterer Fehlerbefund und lokale Korrektur](CRM_ERP_REISEZEITPUNKT_2026-11-09.md).

Die vorangegangene Veröffentlichung 29f526d und ihre Läufe
[Development42697887605](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42697887605)
und [iPhone42697887724](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42697887724)
haben sechs erfolgreiche Development-Jobs; Online-API, Browser und beide
iPhone-Jobs sind beim Nachfolger abgebrochen. Ein vollständiger grüner Lauf
wird für 29f526d nicht behauptet. Der frühere erste Abruf bleibt unverändert:
[damaliger Zwischenstand](evidence/online-command-restart-2026-11-09/publication-initial.json).

**Letzter vollständig grüner Produktstand:** Der gemeinsam geprüfte Produktstand
`19ec4e9dbca6c54dd964075cac6591442abb63ee` ist auf dem autorisierten Testbranch
veröffentlicht; der Remote-Zeiger ist lesend bestätigt. Seine eigenen Läufe
[Development42670555279](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42670555279)
und [iPhone42670554193](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42670554193)
sind abgeschlossen: Alle acht Development-Jobs einschließlich Windows und
Mac-Simulator sowie der unsignierte iPhone-Build bestehen. Der signierte Upload
ist nicht angefordert und übersprungen. Das ist keine neue Serverinstallation
oder Abnahme auf echten Geräten.
[Unveränderter erster Ergebnisabruf](evidence/mileage-integration-2026-11-09/publication-initial.json).
[Abgeschlossene eigene Remoteprüfung](evidence/mileage-integration-2026-11-09/ci-completed.json).
Der Gesamtumfang benötigt weiterhin mehrere Arbeitstage; eine belastbare
Stundenzusage lässt sich aus den offenen Code- und Abnahmeaufgaben nicht ableiten.
Die frühere Angabe von 2–4 Stunden ist keine gültige Gesamtprognose.

Vorangegangener vollständig grün geprüfter Produktcode:
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
`/workspace/smartplan-country-issuer-scope-20261109`; ältere vollständige
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

Die Materialrückgabe ist inzwischen in beiden Clients mit dem vorhandenen
Lagervertrag integriert. Originalentnahme, historische Bewertung, Restmenge,
Teil-/Vollrückgabe, Bestand und Projektkosten sind im tatsächlichen PostgreSQL-/
MFA-/HTTP-/Restore-/Konkurrenz- und Browserablauf geprüft. Die Lagerrolle
benötigt keine Finanzrechte. Ein tatsächlich reproduzierter verspäteter GET
ersetzte einen bereits gewechselten Dialog; der bestehende Guard prüft jetzt
zusätzlich die Dialoggeneration und besteht dieselbe Gegenprobe. Der gemeinsame
Nachlauf besteht 980 Browsermodul- und 41 native Fälle, Appanalyse ohne Befund.
[Integrationsnachweis](CRM_ERP_MATERIALRUECKGABE_INTEGRATION_2026-11-09.md).
Im damaligen Materialstand sind offene Rückgabeaufträge sitzungsgebunden.
Die native Wiederaufnahme ist inzwischen im nachstehenden Originaljournal
ergänzt; Browserpersistenz und Offline-Materialrückgabe bleiben offen.

Die enge Kilometererstattung für dienstliche Mitarbeiterfahrten im privaten
Pkw ist jetzt ebenfalls mit beiden Clients integriert. Ein unabhängiger Root-
Review bestätigt vor Veröffentlichung einen tatsächlichen Doppelbelegfehler
bei teilweise überlappenden Originalmengen. Er ist pro Original-SHA geschlossen;
erhaltene alte Bündel und eigene Korrekturen bleiben unverändert nutzbar.
Beide tatsächlichen negativen Gegenproben bestehen jetzt. Gemeinsamer Stand:
992 Browsermodul-, 65 native, 45 Backend-/Paketfälle sowie ein echter alter
Bündelstand und drei vollständige tatsächliche Browserabläufe (Material,
Kilometer, Katalog) grün. Appanalyse ohne Befund. Der ältere vollständige
App-Lauf bleibt seinem eigenen Stand 8273852 zugeordnet.
[Gesamtintegration und verbleibender Umfang](CRM_ERP_KILOMETER_GESAMTINTEGRATION_2026-11-09.md).

Die native App ergänzt jetzt das
[verschlüsselte Originaljournal für Material und Kilometer](CRM_ERP_ONLINEAUFTRAEGE_NEUSTART_2026-11-09.md).
Nach echtem angenommenem POST, verlorener Antwort und vollständiger Controller-/
Sitzungsneuerstellung wird kein Ersatzauftrag freigegeben. Firmenwechsel mit
identischen Benutzerkennungen, Projektentzug trotz globaler Lagerrechte,
unbekannte Antwort, explizite Nichtannahme und konkurrierende Fenster sind
getrennt geprüft. 89 gemeinsame native Fälle, 42 Backendfälle, fünf tatsächliche
PostgreSQL-/Konkurrenz-/Restorefälle und der echte Materialbrowser bestehen;
Appanalyse ohne Befund. Browserpersistenz offener Aufträge, alte ungebundene
Server, Offline-Rückgaben und reale Geräteabnahme bleiben getrennte Restpunkte.

Die unabhängige Folgeprüfung bestätigt und schließt außerdem einen Rückfall
auf neue RAM-Aufträge bei fehlender Serverfähigkeit trotz erhaltener alter
Originale. Die [schreibfreie Erkennung](CRM_ERP_ORIGINALJOURNAL_SERVER_RUECKFALL_2026-11-09.md)
blockiert in diesem Fall Ersatzaufträge und legt keinen Ersatzschlüssel an.
Die unveränderte tatsächliche HTTP-Gegenprobe sowie alle 95 betroffenen nativen
Fälle bestehen; Appanalyse ohne Befund. Ein wirklich leerer Altserver bleibt
im begrenzten RAM-Verfahren nutzbar. Die Browserintegration ist separat aktiv.

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
Seine eigenen Prüfungen sind beendet:
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
Der Business-/Browserjob scheitert an der alten Erwartung eines zweiten
Entwurfsdialogs trotz offener Originalantwort. Die Anwendung verlangt hier
ausdrücklich Originalklärung; der aktualisierte tatsächliche Katalogablauf
prüft diese Sperre und erhält weiterhin Dialog-/Fokusschutz bei verspäteter
Antwort. Derselbe Ablauf ist auf dem gemeinsamen letzten Stand grün.
[Katalogabnahme und ursprüngliche Fehler](CRM_ERP_KATALOG_OFFENE_BELEGANTWORT_2026-11-09.md).
Der unsignierte iPhone-Lauf scheitert
an drei Service-Journal-Fällen mit nicht aufgelöstem macOS-Temp-Pfad. Genau der
Fehler ist mit unverändertem Server und tatsächlichem Pfadlink reproduziert,
im Testaufbau korrigiert und mit allen drei vollständigen Fällen sowie Analyse
erneut grün. Der produktive POSIX-Guard ist unverändert. Der signierte Upload
bleibt übersprungen. Diese Korrektur ist ebenfalls im Materialkandidaten.
Die vollständige lokale Appprüfung auf genau diesem Stand ist inzwischen grün.
Der signierte Upload ist nicht angefordert.
[Veröffentlichungsnachweis](evidence/final-assembly-2026-11-09/publication.json).
[Zwischenstand der tatsächlichen CI-Ergebnisse](evidence/final-assembly-2026-11-09/ci-827-intermediate.json).
[Abgeschlossene Ergebnisse auf genau 8273852](evidence/final-assembly-2026-11-09/ci-827-completed.json):
fünf Development-Jobs erfolgreich, drei fehlgeschlagen; unsignierter iPhone-
Lauf fehlgeschlagen, signierter Upload übersprungen. Alle vier konkreten
Testaufbau-/Bedienerwartungsursachen sind inzwischen lokal nachgeprüft behoben;
die neue vollständige Remoteprüfung des aktuellen Kandidaten steht noch aus.
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


## 10.11.2026 – echte Anmeldeantwort im Belegrestbetragsbrowser

Der veröffentlichte V5-/SQLite-Stand b31028a besteht Backend, Flutter, Windows,
Mac, HTTPS und Update. Sein Browserjob129627935331 in42755194933 scheitert
später im Belegrestbetragsablauf: Chromium hat den Antwortkörper der
Fähigkeiten während des echten Anmelde-Seitenwechsels verworfen. Die
Einkaufsreparatur wird dadurch nicht als erneut fehlgeschlagen umgedeutet.
Die Beobachtung liest jetzt den tatsächlichen Antwortkörper vor dessen
unveränderter Weitergabe. Kein DTO-Ersatz, kein gelockerter fachlicher Test,
keine verlängerte Zeitgrenze. Der gesamte gezielte Browser besteht mit
Teil-/Restbeträgen, Centbindung, zwei verlorenen Antworten, Rechteentzug,
Altbelegen und Mobilansicht.
[Fehler und tatsächlicher Nachweis](evidence/capacity-login-response-2026-11-10/manifest.json).
Eigene Folge-CI bleibt erforderlich; keine Serverinstallation. Der Gesamtauftrag
läuft weiter, der Faktor-/Anspruchsvertrag V12 wird separat weiterentwickelt.


## 10.11.2026 – V12 gemeinsam technisch abgeschlossen, Gesamtauftrag fortgesetzt

Der vollständige korrigierte App-Lauf besteht mit **1.905 Fällen ohne Fehler
oder Skip** in732.859ms. Die tatsächliche Schlussmeldung lautet success:true.
Der erste1902er-Lauf bleibt mit seinen26 Fehlern im Rohnachweis erhalten.
55 Backend-,1041 Browsermodul-, neun neue App- und21 Paketfälle, saubere
Analyse12,4s sowie der tatsächliche PG-/MFA-/Konkurrenz-/EÜR-/Jahres-/CRLF-/
Restorefall25,979s bestehen. Beide echten Browserabläufe bestehen nach
Zusammenführung mit der Anmeldeantwort-Korrektur erneut. 1.103 Python-/Dart-/
JavaScriptdateien sind gegenüber dem vorherigen geprüften Faktorcode bytegleich;
die zusätzlich integrierte CJS-Testbeobachtung ist gesondert tatsächlich geprüft.
[56 rohe Prüfdateien, vollständige App-Protokolle und Manifest](evidence/factor-claims-2026-11-10/manifest.json).

Produktcode d1f5ba1562a084127466d1f2fd3d9da6671e0dab auf Basis cb7ff63;
Veröffentlichung, eigene CI und tatsächlicher Live-/Gerätestand bleiben
getrennte Nachweise. Der ganze Auftrag läuft weiter. Der nächste konkret
begonnene Abschnitt ist der ausschließlich lesende Abgleich bereits archivierter
alter Offline-Serviceprotokolle: vier tatsächliche MFA-/HTTP-Fälle bestehen im
separaten Arbeitsverzeichnis /workspace/smartplan-legacy-service-recovery-20261110.
Alte Texte oder Unterschriften werden dabei nicht neu übertragen, neue Firmen
nicht aus einer alten ungebundenen Adresse abgeleitet und Altaufträge nicht als
neue Dokumente wiederholt. Diese Folgeentwicklung ist noch nicht veröffentlicht.


## 10.11.2026 – aktive Altprotokollfolge nach V12

R11.03/B/F/G: [Lesender Abgleich alter Serviceprotokolle](CRM_ERP_ALTBERICHT_ABGLEICH_2026-11-10.md)
wird auf d1f5ba1 umgesetzt. Die erste tatsächliche Reproduktion ist404; der
neue begrenzte Backendvertrag besteht danach mit vier echten MFA-/HTTP-Fällen.
Native Quellbindung und Bedienung, ursprüngliche Signatur-/PDF-Prüfung und
weitere gemeinsame Nachweise bleiben aktive Arbeit. Kein alter Text oder
Signaturzug wird hochgeladen, keine Quarantäne automatisch freigegeben und
keine Warteschlange geändert. Der Gesamtauftrag bleibt aktiv.


## 10.11.2026 – gemeinsame Altprotokollprüfung

[Lesender Altprotokollabgleich](CRM_ERP_ALTBERICHT_ABGLEICH_2026-11-10.md):58
Backendfälle,29 native Altbestandsfälle, zusätzlicher echter Zwei-Firmen-/MFA-/
TCP-/PDF-/Dateiabgleich, drei neue und sechs bestehende echte PostgreSQL-/
Restorefälle sowie21 Paketprüfungen und saubere Analyse bestehen. Erste
Test-I/O-/Scroll-/Importfehler bleiben erhalten; Produktwächter wurden nicht
gelockert. Eigene Wegwerfdatenbank nach verifiziertem Abschluss entfernt.
Der vollständige aktuelle App-Lauf bleibt noch aktiv. V12 ist als799c144
veröffentlicht, seine eigene Development42762857917 und iPhone42762857879
laufen; keine neue Serverinstallation oder Geräteabnahme. Der Gesamtauftrag
geht nach dieser Etappe weiter, insbesondere andere Offline-Dokumentarten,
weitere vereinbarte Regel-/Lohn-/EÜR-Fälle und technische Gesamtintegration.
