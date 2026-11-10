# Verbindlicher aktueller Arbeitsstand

Stand: 10.11.2026. Der Auftrag bleibt die vollständige CRM-/ERP-Software gemäß
Nutzerauftrag und unveränderter `CRM_ERP_Gesamtziel.txt`. Eine abgeschlossene
Etappe verkleinert das Gesamtziel nicht und beendet den Auftrag nicht.

## Projekt und verbindliche Quellen

- Hauptprojekt: `/workspace/Smarplan-Hofmann-Workspace`, Branch
  `codex/factor-transition-periods-20261110`.
- Einzig autorisierter Veröffentlichungsbranch:
  `codex/testupdate-0.7-projects-20261104` im bestehenden Repository.
  Kein Force-Push oder Standardbranchwechsel daraus ableiten.
- Originalziel:23863Bytes, SHA-256
  `a4dea28f6de4afd3e36d1549441aad91ce16dad374f56097979cc2d79b07fbf5`.
  Datei und historische Rechenkerne unverändert erhalten.
- Maßgebliche [Anforderungsmatrix](CRM_ERP_ANFORDERUNGEN.md),
  [Umsetzungsplan](CRM_ERP_UMSETZUNGSPLAN.md),
  [Fortschrittsprotokoll](CRM_ERP_FORTSCHRITT.md) und
  [Benutzerhandbuch](CRM_ERP_BENUTZERHANDBUCH.md).
- Festgelegt: Deutschland/EUR, Einzelunternehmen/EÜR, Regelbesteuerung/Ist,
  Standard19%, SKR04, Nettopreise; reguläre Beschäftigte und gewerbliche Minijobs.
  Die frühere Reihenfolge zuerst Projektbetrieb hat Buchhaltung/Lohn nicht
  aus dem Gesamtziel gestrichen.

## Aktuelle RV-Korrektur nach vollständigem Erstlauf

Der erste veröffentlichte RV-Kandidat51c404b ist wegen zweier tatsächlich
reproduzierter Altlohn-Regressionen nicht freigegeben. Der lokale ganze Erstlauf
endet mit2.224Fällen in2.066,372s, einer Fehlprüfung, drei Fehlern und drei
Auslassungen. Zwei Fehler betreffen fehlende ursprüngliche Sparse-Dateien,
zwei den zu früh aufgerufenen neuen RV-Prüfer bei beschädigten Altbelegen.
Die eigene PostgreSQL-Gruppe4 reproduziert denselben Altbelegfehler unabhängig.
Der Erstlauf und die Remotegruppe bleiben rot; erfolgreiche Nachläufe ändern
sie nicht nachträglich.

Die Codekorrektur9a20836 bewahrt die bisherige reine Umschlagprüfung alter
ungebundener Originale; die bestehenden fachlichen Sperren vor Verwendung und
Upgrade bleiben wirksam. Neue RV-Bindungen einschließlich verschachtelter
Profile werden weiter geprüft. Ein zusätzlicher tatsächlicher Dateikatalog mit
101privaten Originalen und einem unveränderten gebundenen RV-Original deckt eine
verwechselte Clientgrenze auf. Dateikatalog und RV-Präfix besitzen jetzt getrennte
Grenzen. Beide41er-Backendnachläufe,40gemeinsame Appfälle,1.119Browsermodulfälle,
wirklicher Browser sowie drei echte PostgreSQL-/Altbeleg-/Restorefälle in68,797s
bestehen. Die App-Analyse meldet keine Befunde. Der vorherige gesamte lokale
App-Lauf besteht2.033Fälle; spätere Ergänzungen sind getrennt geprüft.

Der korrigierte Gesamtkandidat benötigt seinen eigenen eingefrorenen Archiv-
und vollständigen Remote-/Windows-/iPhone-Nachweis. Frühere Läufe42918195752,
42918195769und42918342817 gehören ausschließlich zu51c404b und dürfen nicht als
Prüfung seines Nachfolgers ausgegeben werden. Signierte Vorbereitungen verwenden
weiterhin `prepare_signed_ipa=true`, `upload_to_testflight=false`. Der letzte
vollständig abgeschlossene Lieferstand bleibt bis zum neuen Nachweis V16/4aa0abd.
Konkrete neue Serverbefehle werden nach dem neuen Nachweis im Lieferstand ergänzt.
34reale Gerätefälle bleiben ungeprüft. Keine neue Liveinstallation oder Meldung.

[Umfang und Entwicklungsnachweise](CRM_ERP_MINIJOB_RV_INTEGRATION_2026-11-10.md).
Hauptprojekt `/workspace/Smarplan-Hofmann-Workspace`, separate Arbeitskopie
`/tmp/smartplan-minijob-rv-20261110`, Branch `codex/minijob-rv-lifecycle-20261110`.
Der frühere Workspacepfad ist ein Kompatibilitätslink. Die Verlagerung wegen
voller Platte hat alle2.335Einträge und den Gitstatus geprüft erhalten.
63historische Lohnmodule und das Originalziel bleiben bytegleich.

Ergänzung: Der endgültige RV-Erstlauf besitzt17erfolgreiche und3rote
Development-Gruppen. Neben der getrennt behobenen Altbelegregression ist eine
Nullsekunden-Eingabe im Betriebsmittel-Browsertest korrigiert. Sein tatsächlicher
MFA-/HTTP-Nachlauf einschließlich gespeichertem Rückgabezeitpunkt besteht.
Produktive Betriebsmittellogik bleibt unverändert; vollständiger Nachfolgerlauf
und dessen eigene Paketnachweise bleiben erforderlich.

## Neuester vollständig geprüfter Produktstand: V16

Produktquelle `4aa0abd6d313fcc5d693606dbef1c7193afb0729` ist ausschließlich auf
dem autorisierten Testbranch veröffentlicht. Alle20eigenen Development-Gruppen
42898771085 bestehen:2.199Backendfälle mit3ausgewiesenen Auslassungen,
2.023Appfälle aufLinux, tatsächliche Windowsbauten mit1.975App- und81portablen
Backendfällen, Browser, PostgreSQL, MFA, Isolation, Update und Restore.
Automatischer iPhone-Release211 und tatsächlich signierte Vorbereitung212
42898966618 erfolgreich; endgültige Signatur-/Team-/Keychain-Prüfung sowie
Schlüsselbereinigung bestätigt, TestFlight-Schritt ausgelassen. Konkrete
[Pakete und Grenzen](CRM_ERP_LIEFERSTAND_AKTUELL.md).

Der [belegte V16-Teilmonat](CRM_ERP_FAKTOR_MIDIJOB_TEILMONAT_V16_2026-11-10.md)
und das einzeln entpackte eingefrorene Quellarchiv sind geprüft. Der vollständige
lokale App-Lauf besteht2.023Fälle. Der zusätzliche lokale Backend-Erstaufruf
bleibt wegen4Importfehlern durch den Testaufruf rot; der korrigierte25er-Nachlauf
ist getrennt erfolgreich. Originalziel und61historische Lohnmodule bleiben
bytegleich.31reale Gerätefälle und alleA–G bleiben ungeprüft/offen. Kein neuer
Liveupdate oder TestFlight-Upload. Der zuvor genannte weitere Nettoausgleich
nachV4 ist bereits alsV5 implementiert und geprüft.

## Erhaltener vorheriger Produktnachweis: Bankimport und Personalpflege

Produktquelle `29b02c82a12d4aa1dfc97eaa84638d840882612d` ist auf dem
allein autorisierten Testbranch veröffentlicht. Ihre eigene Development-
Prüfung 42872855464 besteht alle 20 Gruppen: 2.186 Backendfälle in 1.565,117s
mit drei ausdrücklich ausgewiesenen Auslassungen, 2.004 Appfälle (drei
separate PDF-Fälle plus 2.001 Hauptfälle), tatsächliche Windowsbauten,
Browser-, PostgreSQL-, MFA-, Isolations- und Restoregruppen. Die Rohdaten
sind im [Personalmanifest](evidence/employee-account-selection-2026-11-10/manifest.json)
mit dem genauen Quellstand gebunden.

Der [CAMT.053.001.08-Import](CRM_ERP_BANK_CAMT_2026-11-10.md) erhält das
unveränderte Bankoriginal, das festgelegte lokale Schema und beide ausdrücklichen
Bestätigungen. Die [Personal-Kontenauswahl](CRM_ERP_PERSONAL_KONTENAUSWAHL_2026-11-10.md)
erlaubt berechtigte Profilpflege ohne Zugang zur Inhaber-Benutzerverwaltung;
vorhandene Profile bleiben nach Sperrung des Logins korrekt beendbar.
Die native Offline-Konfliktklärung ist ebenfalls enthalten. Vollständige
Providerverbindungen und echte Anbieterdateien werden daraus nicht abgeleitet.

Der zusätzliche lokale App-Gesamtnachlauf wurde durch den Ausfall der
Ausführungsumgebung unterbrochen. Sein Log endet bei 1.229 sichtbaren Erfolgen
und besitzt keinen Abschluss-/Exitstatus; er gilt ausdrücklich nicht als
vollständig bestanden. Der vollständige eigene CI-Appnachweis ist davon
unabhängig erfolgreich. Der ältere Bankstand 4f67bf8 besitzt außerdem seinen
erhaltenen vollständigen lokalen Nachlauf mit 1.997 Fällen.

Konkrete Pakete, Verteilungsstand und Installationsanleitung stehen im
[aktuellen Lieferstand](CRM_ERP_LIEFERSTAND_AKTUELL.md). Der automatische
unsignierte iPhone-Release 209 besteht. Der tatsächliche manuelle Lauf
42873343567 besteht einschließlich signiertem iPhone-/iPad-Paket 210,
Artefakt 13794053691; Signatur-/Team-/Keychain-Prüfung und Schlüsselbereinigung
erfolgreich. TestFlight-Upload bleibt false und sein Schritt ist ausgelassen. Keine neue Liveinstallation, tatsächliche
Geräte-, Fach-, Sicherheits- oder gesamte Produktivfreigabe wird behauptet.

## Quellcode, Prüfstand und Installation sind getrennt

| Stand | Tatsächlich bestätigt |
|---|---|
| Geprüfter veröffentlichter Produktcode |4aa0abd6d313fcc5d693606dbef1c7193afb0729; spätere Belegcommits ändern den Produktcode nicht.|
| Eigene gemeinsame Prüfung |Development42898771085 alle20Gruppen erfolgreich;2.199Backendfälle mit3Auslassungen,2.023Linux-Appfälle, Windowsbau/-Pakete, Browser-/PG-/MFA-/Isolations-/Update-/Restoregruppen.|
| Eigene iPhone-Pakete |Automatischer Release211 und signierte Vorbereitung42898966618/Paket212 erfolgreich. Endgültige Signatur-/Team-/Keychain-Prüfung und Schlüsselbereinigung erfolgreich; Upload ausgelassen.|
| Getrennte neue Codearbeit |Eigene Arbeitskopie/workspace/smartplan-minijob-rv-20261110 aufBasis4aa0abd; RV-Komponenten-/Speicherweg noch nicht vollständig mit Profil, Lohn, Clients und Geld-/Restoreweg verbunden.|
| Letzte bestätigte Serverinstallation |a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5, Nutzerbestätigung05.11.; keine neuere Installation behauptet.|
| Reale Geräte-/Fach-/Sicherheitsabnahme |31Gerätefälle ungeprüft; A–G offen; keine beauftragte oder durchgeführte unabhängige Gesamtfreigabe.|


## Historischer Vorbereitungsabschnitt: signiertes iPhone-Paket getrennt vom Upload

Arbeitskopie `/workspace/smartplan-ios-signed-preparation-20261110`, Branch
`codex/ios-signed-preparation-20261110`. Produkt12798fb, veröffentlicht in deebe20. Der geprüfte neue
[Vorbereitungsweg](CRM_ERP_IPHONE_SIGNIERTE_VORBEREITUNG_2026-11-10.md) erlaubt
die signierte Paketvorbereitung auf dem exakten autorisierten Testbranch und
verlangt eine eigene ausdrückliche Auswahl für den TestFlight-Upload.
33 lokale Auslieferungs-/Paket-/CI-Fälle,48 tatsächliche Gate-Kombinationen sowie
YAML- und Bash-Syntax bestehen. App-/Backend-/Browsercode bleibt bytegleich zum
vollständig geprüften Installationsstand. Bestehende Apple-Einrichtung wurde
schon für Build108 verwendet. Der wirkliche Lauf42796610215 bestätigt die bestehende
Apple-Einrichtung: Archiv und signierter Export erfolgreich; die folgende Prüfung
verweigert das Paket wegen fehlender Keychain-Berechtigung. Keine Veröffentlichung
des defekten Pakets und kein TestFlight-Upload. Der vollständige Development-Lauf
42796495383 besteht alle20 Gruppen.

Die lokal geprüfte Reparatur fordert genau die eigene Keychain-Gruppe an und
übernimmt deren tatsächlichen App-ID-Präfix aus Apples signiertem Export und
Profil. Eine ausschließlich temporäre Archivsignatur erhält diese Berechtigung
für den zweiten, endgültigen Apple-Export. Der endgültige Export muss erneut
Codesignatur, echtes Distributionsteam, eigene konkrete Gruppe, Debuggersperre
und Quell-/Paketkennung bestehen. Temporäre Pakete sind kein Uploadartefakt.
39 gemeinsame lokale Paket-/Auslieferungs-/CI-Fälle bestehen in33,283s; alle22
Shellblöcke und YAML sind geprüft. Die Reparatur40d8fcf ist ausschließlich auf dem autorisierten Testbranch veröffentlicht
und der Remote-Zeiger bestätigt. GitHub hat den erneuten manuellen Vorbereitungslauf
42806142665 mitprepare_signed_ipa=true undupload_to_testflight=false angenommen.
Beide Jobs sind inzwischen erfolgreich abgeschlossen. Der endgültige reparierte
Export besteht seine tatsächliche Signatur-/Team-/Keychain-Prüfung. Signiertes
Artefakt Smartplan-Office-iOS-198:13762109533,29866901Bytes, noch ohne V14.
Schlüsselbereinigung besteht, TestFlight-Uploadskipped. Eigene Development-Prüfung
42806104268 besteht alle20 Gruppen.
Der doppelte Push-iPhone42806103960 wurde durch bestehende concurrency ersetzt.
TestFlight-Upload bleibt ausdrücklichfalse.

## Aktive Gesamtprüfung: Faktor-/Midijob V14 und Mitarbeiterbeleg-Leser

Arbeitskopie /workspace/smartplan-factor-transition-20261110, Branch
codex/factor-transition-20261110. Produkt e70b135, lokal mit der getrennten
Keychain-Reparatur und deren Nachweisen zu13b9092 integriert. Der aktuelle
Kandidat ist als91fa18b auf dem autorisierten Testbranch veröffentlicht und der Remote-Zeiger bestätigt;
eigene neue Remoteprüfung besteht inzwischen alle20 Gruppen; Installation bleibt getrennt. Der vollständige tatsächliche
App-Lauf an13b9092 ist abgeschlossen:1961 sichtbare Fälle, kein Fehler/Skip,
260 verborgene Ladeeinträge ausgeschlossen, success:true1437145ms, Exit0 nach
1446,014s. Der vollständige Backendlauf endet um12:32:14UTC erfolgreich:2133 Fälle,
2130 erfolgreich und drei ausdrücklich übersprungen, keine Fehler,2757,214s.
Zwei PG-Gegenprüfungen benötigen einen separaten Test-DSN, die Windows-
Prozessbereinigung läuft ausschließlich in Windows-CI. V14 besitzt daneben
einen tatsächlichen eigenen PostgreSQL-/Restore-Nachweis.
[Enger V14-Vertrag und aktuelle Rohdaten](CRM_ERP_FAKTOR_MIDIJOB_V14_2026-11-10.md).

- Genau ein belegter voller2026-Monat, reguläre KlasseIV mit echtem Faktor,
  unveränderter Monatsvertrag und separate private Zwölfmonatsprognose.
 32 unabhängige XML-Steuerreferenzen und neun DRV-Beitragsbasen geprüft.
 55 bestehende Lohnmodule bytegleich; Originalprofil bleibt unverändert.
- Browser/App mit tatsächlicher Prognoseauswahl, Vorschau, ausdrücklicher
  Bestätigung und unverändertem Wiederholungsauftrag nach verlorener Antwort.
 1077 gesamte Browser-Vertragstests, acht neue native Faktor-Fälle, saubere
  Appanalyse12,4s und wirklicher MFA-/Chromium-/390px-/Widerrufsablauf bestehen.
- Echte PostgreSQL-/MFA-/Parallelitäts-/Cash-/EÜR-/Jahres-/CRLF-/volle Restorekette
  besteht54,205s. Bei1000Euro Brutto: Basen854,06/568,36, Netto874,67,
  EÜR874,67, Vorsteuer0. Alte Sitzung nach Restore401, neue echte MFA besteht.
- Gefundene beidseitige Mitarbeiterbeleg-Leserlücke für V10–V14 ist korrigiert.
  Elf aus tatsächlichen API-Läufen mit unverändertem Projektor/Renderer erzeugte
  reduzierte JSON-/PDF-Belege bestehen in17 Browser- und18 Appfällen. Unbekannte
  oder vertauschte Regeln/Umfänge, private Ergänzungen und Fremdzugriff bleiben
  gesperrt. Kein historischer Beleg oder PDF wird umgeschrieben.
- 58 gemeinsame Backend-/Belegprojektions-/CI-/Paketfälle bestehen61,686s;
  nach Integration der iPhone-Reparatur weitere33 Paket-/Auslieferungs-/Inventar-
  fälle39,748s. Zusätzliche Korrektur bewahrt alte Fälle, Läufe, PDFs und Quittungen.
  Die vollständigen aktuellen App- und Backend-Schlussmeldungen liegen vor;
  eigene neue Remoteprüfung besteht alle20 Gruppen.

Vorfehler einschließlich echter400 bei widersprüchlichem PG-Testprofil,
Widget-Test-Timeraufbau und lokalem Zeitzonen-Unterprozess-EPERM bleiben
unverändert erhalten. Beide eigenen PG-Container sind geprüft entfernt.

## Abgeschlossen: Installationsstand und vollständige Serverarchive

Arbeitskopie `/workspace/smartplan-installation-context-20261110`, Branch
`codex/installation-context-20261110`. Produktcode7449027 und veröffentlichter
Teststand c4a2d8f sind eingecheckt; aktuelle Nachweispflege liegt gegebenenfalls
nur hier.
[Vertrag, Änderungen und Grenzen](CRM_ERP_INSTALLIERTER_QUELLSTAND_2026-11-10.md),
[rohe Nachweise](evidence/installation-context-2026-11-10/manifest.json).

Implementiert und tatsächlich geprüft:

- Eigene beim Paketieren erzeugte, nur gelesene Quellkennung. Pro laufender App
  beim Start eingefroren; fehlender/ungültiger Marker bleibt ausdrücklich
  unerfasst. Aktuelle globale Administrationsrechte und Online-MFA erforderlich.
- Verständliche Supportanzeige in Browser/App; alte Server werden ohne neue
  Fähigkeit nicht angefragt. Widerruf und spätes Ergebnis werden berücksichtigt.
- Beide Betreiberbefehle archivieren den festgelegten Commit. Die Erstinstallation
  enthält nun auch die zuvor fehlenden Browserdateien.
- 1058 gesamte Browser-Vertragstests;35 gemeinsame HTTP-/CI-/Archiv-/Paket-/
  Inventarfälle; zehn native Einstellungsfälle; saubere Analyse25,4s; echter
  MFA-/Chromium-/390px-/Widerrufsablauf.
- 88 vollständige endgültige isolierte Betreiberfälle in661,167s.
  Wirkliches7449027-Gitarchiv in eigenem Interpreter mit MFA, Paketkennung und
  fünf Browser-Einstiegsdateien geprüft (4,629s).
- Echter PG-/Runtime-/MFA-/vollständiger Restorefall30,201s. Alte Sitzung nach
  Restore401, danach tatsächliche neue MFA-Anmeldung. Alle vier eigenen PG-
  Container nach voller ID/Label/Loopback geprüft entfernt; fremde unverändert.

Die vollständige aktuelle App-Suite ist abgeschlossen: **1939 sichtbare Fälle,
kein Fehler und kein Skip**, tatsächliche success:true-Schlussmeldung1429392ms,
Runner1436,017s.258 verborgene Ladeeinträge werden nicht mitgezählt. Rohbericht,
Schlussstatus und unabhängige Zählung sind im verlinkten Nachweisarchiv gesichert.
Die gezielte Remote-Wiederholung nach dem Werkzeugdownloadfehler und der eigene
unsignierte iPhone-Release sind ebenfalls erfolgreich abgeschlossen. Die erste
gescheiterte Downloadphase bleibt getrennt erhalten; sämtliche13 ausgewählten
Browserabläufe bestehen in der Wiederholung unverändert.

## Abgeschlossener Vorgänger: Faktor, Ansprüche und bereits bezahlte Reisen

[Begrenzter V13-Vertrag](CRM_ERP_FAKTOR_ANSPRUECHE_BEZAHLTE_REISEN_V13_2026-11-10.md)
verbindet unveränderte V12-Lohn- und V10-Reiseoriginale. Bereits gezahlte Reise
wird nicht erneut zum Netto addiert. Vollständige Verwendungshistorie ist vor
Ergänzung eines unbenutzten Altfalles erforderlich; fehlendes Journal gilt nicht
als leerer Bestand. Alte Rechenkerne, Quittungen und Projektstunden bleiben erhalten.

1934 tatsächliche gesamte Appfälle ohne Fehler/Skip,1056 Browsermodule,48
Backend-/CRLF-/CI-Fälle,21 Paketfälle, drei reale Browserabläufe und tatsächliche
PG-/MFA-/Parallelitäts-/EÜR-/Jahres-/volle Restoreketten bestehen. Alle20 eigenen
Remotegruppen und unsignierter iPhone-Release sind erfolgreich.
[Genauer abgeschlossener Nachweis](evidence/factor-claims-paid-travel-2026-11-10/manifest.json).
Die aktuelle App-Gesamtprüfung darf nicht aus diesem Vorgängerwert abgeleitet werden.

## Weiterarbeiten bis zum Gesamtziel

1. Den integrierten V14-Stand mit abgeschlossenem1961-Appnachweis und gezielten
   Finanz-/Client-/PG-Prüfungen weiter bis zum tatsächlichen Backend- und
   eigenen Remote-/Paketabschluss bringen. Der Keychain-Reparaturstand40d8fcf
   besitzt inzwischen sein wirkliches signiertes Paket198.
   Keinen TestFlight-Upload aus der Paketvorbereitung ableiten.
2. Nur tatsächlich überprüfte Ergebnisse in Matrix, Plan, Fortschritt und diese
   aktuelle Zusammenfassung übernehmen. Neue Nachweispushes nicht unnötig so
   auslösen, dass noch benötigte laufende CI durch concurrency abgebrochen wird.
3. Verbleibende Code-/Abnahmepunkte anhand des Gesamtziels weiter abarbeiten.
   Bekannte Lohnfolgefälle stehen im [Lückenplan](CRM_ERP_LOHN_LUECKENPLAN_2026.md)
   und [Source5-Restplan](CRM_ERP_SOURCE5_MEHRFACH_GRUPPEN_RESTPLAN_2026.md).
   Verwendete V10-/V12-Altfälle besitzen noch keinen vollständigen neuen
   Korrekturvertrag. Weitere Steuer-/Faktor-/Einmalbezugsfälle nicht durch
   stillschweigende Freigabe bestehender Sperren ergänzen.
4. Tatsächliche HERO-/sevDesk-Originale, ausgewählte Drittanbieterzugänge,
   signierte iPhone-Verteilung, reale Geräte-/Betriebsabnahme und unabhängige
   Fach-/Sicherheitsprüfung bleiben konkrete externe Nachweise. Vorbereitete
   synthetische Prüfungen oder ein gebautes Programm ersetzen sie nicht.
5. Keine echten Nachrichten, Zahlungen, Meldungen, produktiven Migrationen oder
   öffentlichen Veröffentlichungen aus der Entwicklungsbeauftragung ableiten.
   Testbranch-Veröffentlichung ist bereits ausdrücklich autorisiert.

Das [konkrete externe Abnahmepaket](CRM_ERP_EXTERNER_ABNAHMEAUFTRAG_2026-11-10.md)
ist vorbereitet. Die Benennung zuständiger Fach-/Sicherheitsprüfer ist beim Nutzer
nicht blockierend angefragt; eine Antwort oder Freigabe liegt noch nicht vor.

Die übrigen CRM-/Projekt-/Angebots-/Rechnungs-/Zeit-/Einkaufs-/Service-/EÜR-/
Assistenten-/Offlinebausteine haben abgegrenzte technische Nachweise; die Matrix
führt den vereinbarten Umfang je Anforderung. Keines der offenen A–G wird aus
Testzahlen allein produktiv freigegeben. Es gibt keine belastbare Gesamtprozentzahl.

## Historie und Wiederaufnahme

Alle früheren Momentaufnahmen einschließlich widersprüchlicher damaliger
Zwischenstände bleiben unverändert in der
[Arbeitsstandshistorie bis10.11.](CRM_ERP_ARBEITSSTAND_HISTORIE_BIS_2026-11-10.md).
Für den aktuellen Zustand zuerst dieses Dokument lesen. Das technische
Fortsetzungsregister `/tmp/smartplan-active-integration-20261109.json` nennt
Arbeitskopien, Quellstände, laufende Prüfungen und Rohdateien; es ersetzt keine
im Repository abgeschlossenen Nachweise. Bestehende Branches/Arbeitskopien und
lokale Änderungen erhalten. Keine neuen Agenten ohne ausdrückliche Anweisung.

## Aktive Fortsetzung: ausgewählte Bank- und Lieferantenanbindungen

Direkte Nutzerentscheidung10.11.: Qonto, Sparkasse, Amex; Lieferanten Granzow,
Alexander Bürkle, Loxone und Voltus. Genaue Sparkasse und Amex Business/Corporate
sind noch angefragt. Keine Zugangsdaten wurden im Chat verlangt oder übernommen.

[Qonto-Leseabschnitt und gewählte Anbieter](CRM_ERP_BANK_LIEFERANTEN_ANBINDUNGEN_2026-11-10.md) ist als Produkt01c368f lokal eingecheckt:
serverseitig lesende V2-Organisation und begrenzte Umsatzänderungen, exakte
Centbeträge, alle vier Status, aktuelle Bank-/Finanz-/Buchführungsrechte vor/nach
Anbieterkommunikation, ohne SQL-Lock über IO. Browser und App öffnen die neue
Ansicht aus dem Bankabgleich und kennzeichnen fehlende Einrichtung. Keine
automatische Buchung, kein erfundener vollständiger Kontoauszug.

59 gemeinsame Backend-/Transport-/CI-/Paketfälle37,742s,1081 gesamte
Browsermodule25,098s,15 gezielte native Fälle und saubere Appanalyse16,3s
bestehen. Tatsächlicher MFA-/Chromium-/390px-/Abmeldeablauf sowie echte
getrennte PostgreSQL-Runtime mit erhaltenen Cash-/Bankoriginalen, vollständigem
Dump/Restore, alter401 und neuer tatsächlicher MFA bestehen33,452s.
Alle41 Rohdateien samt Erstfehlern sind hash-/bytegeprüft archiviert.
Der erste PG-Container scheitert vor Tests am vollen Volume, wird anhand exakter
ID/Markierung geprüft entfernt; Wiederholung mit begrenztem512MiB-Tmpfs besteht.
Keine fremden Container bereinigt.57 Lohnmodule und Originalziel bleiben bytegleich.

Qonto-Zugang ist in diesem Abschnitt nur ein geschütztes Betreiber-OAuth-Token.
OAuth-Einwilligung/automatische Erneuerung, tatsächlicher Zugang, Feed-Originalarchiv
und Einbindung als geprüfter Auszug bleiben offen. Keine Bankgeheimnisse und
neuen Provider-Zielhosts in dieser Cloud vorhanden. Für Loxone sind offizielle
EUR-/CHF-CSV und DATANORM4/5 recherchiert; die CSV-Weiterleitung ist über das
Recherchewerkzeug nicht lesbar, DATANORM erfordert Shopanmeldung. Kein
Dateischema geraten. Granzow-/AB-Protokollangebote und Voltus-IDS2.5 sind
recherchiert; Vertrags-/Partnerzugänge und echte Anbieterabnahme fehlen.
Eigener neuer Push/CI und reale Server-/Geräteinstallation werden separat geführt.

## Lokal abgeschlossen: Qonto-Eigenkonto-Key nach verifiziertem Vertrag

Produkt67b99d3 ergänzt ausdrücklich den offiziellen Eigenkonto-Key-Modus,
Header exakt Sign-in:Secret-Key ohne Basic/Bearer/Base64. Der vorherige
OAuth-Modus bleibt erhalten. Organisations-UUID/IBAN und frische Rechte
werden in beiden Modi weiter geprüft. Geheimnisse und Sign-in gelangen nicht
in öffentliche Statusansichten oder Objekt-Repräsentationen. Kein Key-Zugang
für fremde Kunden anstelle des dafür erforderlichen OAuth behauptet.

43 gemeinsame Anmelde-/Transport-/MFA-/Frischerechte-/CI-Fälle10,469s,
beide tatsächlichen PG-/MFA-/Cash-/Original-/Dump-/Restorefälle41,810s
und wirklicher Eigenkonto-Key-/Browser-/390px-/Abmeldeablauf bestehen.
Clientruntime bleibt bytegleich zu ca14; ein zusätzlicher tatsächlicher
Quellarchivfall besteht.16 Rohdateien samt ursprünglichem roten Vertrag,
Primärquelle und tatsächlichem Apple-Netzwerkfehler sind archiviert.
Dieser Zusatz wird lokal gehalten, während die eigene ca14-CI läuft; keine
unnötige Verdrängung der aktiven vollständigen Prüfung. Keine Liveverbindung.

Loxone-Direktabruf: nach Proxy-Verbindungsfehler im normalen Sandboxaufruf
antwortet derselbe öffentliche HTTPS-Abruf mit regulärer Genehmigung403 von
Envoy. Aktuelle erzwungene Hostfreigabe enthält pim.loxone.com nicht. Der Nutzer
ist um genau diese zusätzliche Freigabe in den Einstellungen gebeten; kein
Konfigurationswerkzeug verfügbar, kein Umgehen der Netzrichtlinie. Andere
Arbeiten laufen weiter. Quellen und bestehende Freigaben bleiben erhalten.

## Aktive Codearbeit: Faktor-Einmalbezug nach eigenem Jahresvertrag

Arbeitskopie /workspace/smartplan-factor-transition-20261110, neuer Branch
codex/factor-oneoff-20261110 an5c779b9. Der ursprüngliche V14-Branch ist erhalten.
Reiner neuer Steuerbaustein mit344 unabhängigen XML-Vektoren und20 gemeinsamen
Fällen geprüft; keine Registrierung oder neue Client-/Zahlungsfreigabe.
Die tatsächlich festgestellte alte Jahres-V1-Grenze wird durch einen ausdrücklichen
versionierten Quellenweg ergänzt. [Umfang und nächste Schritte](CRM_ERP_FAKTOR_EINMALBEZUG_V15_PLAN_2026-11-10.md).
Qonto-/Apple-/Netzwerknachweise bleiben davon getrennt erhalten.



## Tatsächlicher iPhone-Nachlauf erfolgreich

[Signiertes Paket200](CRM_ERP_IPHONE_SIGNIERTES_PAKET_200_2026-11-10.md) an91fa18b:
Wiederholungsjob129852986325 erfolgreich, beide Apple-Exporte, strenge finale
Signatur-/Team-/Keychain-Prüfung und Bereinigung bestehen. Artefakt13769975157
mit29898645Bytes vorhanden; TestFlight-Uploadskipped. V14 enthalten, Qonto noch
nicht enthalten. Der tatsächliche erste Netzwerkfehler bleibt erhalten.
Keine neue Geräteinstallation oder Serveraktualisierung daraus ableiten.


Aktueller Nachlauf: ca14af3/Development42821768166 ist mit allen20 Gruppen
erfolgreich abgeschlossen. Eigenkonto-Key67b99d3 samt Nachweisen wird jetzt
für den autorisierten Testbranch veröffentlicht. Die neue eigene Remoteprüfung
bleibt vom abgeschlossenen Vorläufer getrennt. Keine Liveinstallation.


## Eigene Qonto-CI und ergänzte Nutzerentscheidungen10.11.

Quellstand51c731a: alle20 eigenen Development-Gruppen erfolgreich, tatsächliche
Appsuite1962 Fälle, Backend2133 mit3 Auslassungen; eigener unsignierter
iPhone-Build202 erfolgreich. Neue signierte Vorbereitung scheitert zunächst
an fehlender Runnerzuweisung (kein Schritt ausgeführt); genau ein gezielter
Wiederholungsversuch läuft. Signiertes V14-Paket200 bleibt eigener Nachweis;
kein TestFlight-Upload oder neues Serverupdate.23 Rohdateien im
Eigenkonto-Manifest sind geprüft.

Nutzer hat Kreissparkasse Rottweil und Amex Business-Karte präzisiert und
Loxones Hostfreigabe auf später verschoben. Die Bedeutung der unabhängigen
Fach-/Sicherheitsabnahme ist erklärt; keine Prüfer benannt oder beauftragt.
Direkte Providerfreigaben bleiben externe Schritte. Die laufende V15-Arbeitskopie
hat inzwischen eine vollständige tatsächliche PostgreSQL-/Geld-/Jahres-/
Restorekette bestanden; ihre Client- und gemeinsame Schlussprüfung läuft noch.


## 10.11.2026 – Faktor-Einmalbezug V15 lokal vollständig verbunden und gemeinsam geprüft

Implementierung54825d9, Integration mit erhaltenen Qonto-/Apple-Nachweisenf14fe7f.
Der eigene geplante Jahresvertrag V2 bindet unveränderte tatsächliche Faktor-/P4-
Monatsfälle; der V15-Einmalfall und sein Source4-Lauf erhalten die gemeinsame
Anspruchsgrenze, ursprüngliche Profile, Quellen, bezahlte Teilbeträge und historische
Quittungen. Zahlungen, Netto-/Abgaben-Cash, EÜR und Jahresbasis sind verbunden.
Der reduzierte Mitarbeiterbeleg erhält Schema5 mit festen Regel-/Umfangspaaren.
Neue private Auswahl und getrennte Wiederholungskennungen in Browser und App.

Tatsächliche Nachweise:1.971 vollständige lokale Appfälle21:48,1.086 vollständige
Browserverträge28,681s,28 gemeinsame native Bedien-/Belegfälle und sechs zusätzliche
Faktor-/Jahres-/Wiederholungsfälle. Tatsächlicher Browser mit MFA, unverändertem
Wiederholen zweier verlorener erfolgreicher Antworten, Original-PDF, eigener
Mitarbeiterbelegnavigation ohne private Quellaufrufe und390px besteht. Der dabei
gefundene gemeinsame Wiederholungsrouterfehler ist korrigiert; Erstfehler erhalten.

Vollständiger neuer PostgreSQL-/MFA-/Konkurrenz-/Cash-/EÜR-/Jahres-/Restorefall
1/76,023s besteht; eigene begrenzte Datenbank nach verifizierter exakter ID entfernt.
69 vorausgehende Jahres-/Regressions-/Paketfälle bestehen. Die gemeinsame neue/
alte48er-Backendgruppe298,029s hat47 erfolgreiche Fälle und einen nicht startbaren
alten HTTP-Test wegen Sandbox-Socketrechten; genau dieser besteht anschließend
mit regulärer Loopback-Freigabe1/6,157s.31 Paket-/CI-/Inventar-/Archivfälle32,201s,
tatsächlicher eingefrorener MFA-Archivstart1/4,929s und20 Auslieferungsrichtlinien-
fälle2,002s bestehen. Appanalyse ohne Probleme.153 Abhängigkeitskomponenten stimmen
mit der bestehenden Stückliste überein;57 alte Lohnmodule und das Originalziel
bleiben bytegleich. Die Rohdateien, Fehlversuche, Bilder und Grenzen stehen im
[V15-Manifest](evidence/factor-oneoff-2026-11-10/manifest.json).

Beide zusätzlichen51c-Signieraufträge endeten ohne zugewiesenen Runner und ohne
Schritte. Der nächste Signierjob verwendet deshalb denselben konkreten Mac-Typ
macos-26-intel wie der erfolgreiche unsignierte Release. Das ist noch kein neuer
Signiererfolg; Upload bleibtfalse. Tatsächlich signiertes V14-Paket200 bleibt
vorhanden. Neuer Testbranch-/eigener CI-/Windows-/iPhone-Nachlauf folgt erst nach
tatsächlichem Push. Kein Serverupdate, keine Geräte-/Fach-/Produktivfreigabe.

Kreissparkasse Rottweil und Amex Business sind festgehalten; Loxone-Hostfreigabe
vom Nutzer auf später verschoben. Abschlussprüfung ist verständlich erklärt,
noch keine Prüfer benannt oder beauftragt. Weitere direkte Providerwege und
benannte Lohnfälle, insbesondere die ungeklärte Source5-Steuergruppe, bleiben
aktiv offen. R09.03/D und die übrigen Gesamtabnahmen werden nicht geschlossen.


## 10.11.2026 – V15 tatsächlich veröffentlicht, eigene Remoteprüfung läuft

Der lokal geprüfte Gesamtstand1fa0bcceb28a822bed9600ad18e33ba54d2c227f ist
nach Fast-forward im Hauptprojekt /workspace/Smarplan-Hofmann-Workspace
und ohne Force ausschließlich auf codex/testupdate-0.7-projects-20261104
veröffentlicht. Remote-Hash ist tatsächlich erneut gelesen und identisch.
Der endgültige eingefrorene Archiv-/MFA-Laufzeitstart besteht1/7,390s.
Die eigene Development-Prüfung42842985262 und der unsignierte iPhone-Lauf
42842985277 sind gestartet. Zusätzliche signierte Vorbereitung mit
prepare_signed_ipa=true und upload_to_testflight=false ist angenommen.
Keine dieser neuen Remoteprüfungen wird vor ihrem Abschluss als bestanden
behauptet; alte51c-Ergebnisse bleiben eigene Nachweise. Kein Liveupdate.

Auf Nutzerfrage zum Prozentstand: Die unveränderte Matrix enthält62
Hauptanforderungen:24 implementiert,16 getestet,6 teilweise,11 offen,5 extern
blockiert.40/62 entsprechen rund65 Prozent der erfassten Anforderungen. Das
ist eine ungewichtete Statusquote, keine Aussage über Restaufwand oder
produktive Einsatzbereitschaft. Zusätzliche V15-Prüfungen schließen die
übergeordneten Lohn-/Gesamtabnahmen nicht pauschal.


## 10.11.2026 – V15 vollständig grün; native Offline-Konfliktklärung lokal abgeschlossen

Veröffentlichter Gesamtstand1fa0bcceb28a822bed9600ad18e33ba54d2c227f besteht alle20
Development42842985262-Jobs einschließlich Windows-Kompilierung und realer
Browser-/PostgreSQLgruppen. Tatsächlicher Backendabschluss:2.152 Fälle in
1.657,445s, drei ausdrücklich übersprungene Fälle. Eigene Linux-Flutterauswahl:
1.968 erfolgreiche Fälle; der bereits erhaltene lokale1971er-Gesamtlauf hat
seine eigene Auswahl. Vollständige Rohlogs und Artefakt-IDs sind im V15-Manifest.
Auch der eigene unsignierte iPhone-Release204 von42842985277 ist erfolgreich:
Artefakt13779244653,15.037.649 Bytes, SHA256
60c5c6502c246263fbb3bd5fb44e7fad0b51518dc3a411cbbe2062e5b3e1e1ad.
Manuelle signierte Vorbereitung42843099650 noch aktiv, Uploadfalse.

R11.03/F/G: [Native Konfliktklärung](CRM_ERP_OFFLINE_KONFLIKTKLAERUNG_2026-11-10.md)
behebt die bislang nicht bedienbare Pause nach geänderten Projekt-/Kundennamen.
Die nur lesende enge Geräte-Diagnose unterscheidet Originalbestätigung,
wieder passenden Stand und tatsächlichen Kontextwechsel. Unverändertes
Original wiederholen oder ausdrücklich einen neu zu unterschreibenden Entwurf
anlegen; verschlüsseltes Altkommando und alte Unterschrift bleiben erhalten.
Ältere Server, heutige Rechte, Kontosperre, konkurrierende Entscheidungen,
verlorene Antwort, Geräte-Neustart und Speicherausfall sind berücksichtigt.

30 gemeinsame Backendfälle28,246s, zwei wirkliche PG-/Dump-/Restoreläufe18,974s
und20,113s,36 gemeinsame native Fälle19s sowie30 Paket-/Inventar-/CI-Fälle28,006s
bestehen. Sechs gerenderte390px-Bilder mit Produktthema und wirklicher Schrift
sind gesichert und visuell geprüft. Erste tatsächliche Transportfehler und
rote Testeinrichtungsstände bleiben erhalten.61 bestehende aktuelle Lohnmodule
und das Originalziel bleiben bytegleich, keine Schema-/Laufzeitabhängigkeitsänderung.
[35 rohe Nachweise](evidence/offline-report-conflicts-2026-11-10/manifest.json).
Diese neue Folge ist noch nicht veröffentlicht; neue eigene CI folgt nach Push.

Keine neue Liveinstallation, kein TestFlight-Upload und keine reale Geräte-,
Lohn-/Buchhaltungs- oder unabhängige Sicherheitsabnahme. Kreissparkasse Rottweil
und Amex Business sind in der Matrix konkretisiert; die Loxone-Hostfreigabe bleibt
auf Nutzerwunsch vertagt. Andere Dokument-/Konfliktarten, verbleibende benannte
Regel-/Providerfälle und die ganze A–G-Abnahme bleiben im Gesamtauftrag offen.


## 10.11.2026 – native Konfliktklärung als eigener Teststand veröffentlicht

abcc3510f4d913b1d4e57c30fd2e5283bce2156b ist ausschließlich auf dem autorisierten
Testbranch veröffentlicht; der tatsächliche Remote-Zeiger ist identisch.
Der echte Start genau dieses eingefrorenen Quellarchivs besteht mit MFA und
Browser-Einstiegspunkten1/4,655s.38 Rohdateien einschließlich aller frühen
Fehler bleiben im Konfliktmanifest gesichert. Eigene Development42850956041
und unsignierter iPhone-Lauf42850955774 sind gestartet; noch kein Ergebnis
vorweggenommen. Mailbot-Vertragsprüfung42850955711 besteht, kein Mailversand.
Zusätzliche32 bestehende Firmenbindungs-/Zwei-Firmen-HTTP-/Zeit-/Fotofälle
bestehen; abschließende Appanalyse mit Produktthema ohne Probleme31,5s.
Keine neue Liveinstallation oder Geräte-/Fachfreigabe. V15 von1fa0bcc besitzt
bereits alle20 Developmentgruppen und seinen unsignierten iPhone-Release204;
seine manuelle signierte Vorbereitung42843099650 bleibt separat aktiv,
Uploadfalse. Nächste technische Bestandsprüfung: standardisierter Bankauszugs-
Originalimport gegen die offiziellen Formatquellen; noch kein CAMT-Vertrag
freigeschaltet und keine reale Bank-/Lieferantenkommunikation.

## 10.11.2026 – vollständiger lokaler Appnachlauf zum XML-Bankstand

Der veröffentlichte Stand 4f67bf8 besitzt jetzt einen vollständig beendeten
lokalen Appnachlauf: 1.997 Fälle, keine Fehler oder Auslassungen, gemeldete
Dauer 20:49. Der Code während dieses Laufs ist unverändert zum eingefrorenen
XML-Bankstand; neue Personal-Kontenauswahl wird getrennt in der Arbeitskopie
/workspace/smartplan-employee-account-selection-20261110 bearbeitet. Die eigene
Development-Prüfung 42864815919 und manuelle signierte Vorbereitung
42864950880 werden separat weiter verfolgt; Upload false. Kein Abschluss
eines noch laufenden Pakets, kein neues Liveupdate und keine Gesamtabnahme
wird aus dem lokalen Testerfolg abgeleitet.

## Eigene Plattformprüfung des veröffentlichten XML-Bankstands

Development 42864815919 an 4f67bf8 besteht alle 20 Gruppen. Damit sind
auch der tatsächliche Windowsbau mit XML-Parser und Schema, die neuen
PostgreSQL-/MFA-/Restorefälle sowie der neue Browser-Bankablauf im eigenen
veröffentlichten Gesamtstand bestätigt. Windows-Komplettpaket: Artefakt
13788890572, 40.629.752 Bytes, SHA256
4eb01d0fe4d42e01e292d80abe33ab50ad0ec1436146de6d9ae05d8a3fc6d729.
Windows-Onlinepaket: Artefakt 13788027574, 22.255.008 Bytes, SHA256
e3805783925bb4577965f91b3e0472a67465c44bec582e26b4ebfaaa68e4864b.
Der getrennte manuelle iPhone-Lauf 42864950880 ist noch aktiv; daraus wird
noch kein signiertes Paket abgeleitet. Upload bleibt false. Neue
Personal-Kontenauswahl wird getrennt geprüft und ist noch nicht veröffentlicht.

## 10.11.2026 – integrierte Personal-Kontenauswahl und abgeschlossene iPhone-Pakete

Die separat geprüfte Personal-Korrektur 495ee63 ist als 56d9925 in das
Hauptprojekt integriert; alle zehn geänderten Dateien sind bytegleich.
Direkt im Hauptprojekt bestehen zusätzlich vier tatsächliche MFA-/HTTP-/
Quellarchivfälle in 6,847s und sieben Appfälle. Personalauswahl, geschützte
Bearbeitung und das Beenden bestehender Profile nach Kontosperre sind damit
konkret geprüft. Kein Zugang zur vollständigen Benutzerverwaltung wurde
für Personalrollen geöffnet. Der neue Stand wird gesondert veröffentlicht
und erhält seine eigene vollständige Plattformprüfung.

Der vorherige veröffentlichte Bankstand 4f67bf8 hat jetzt neben allen 20
Developmentgruppen und 1.997 lokalen Appfällen auch den automatischen
unsignierten iPhone-Release 207 aus 42864818725 bestanden. Der tatsächliche
manuelle Lauf 42864950880 besteht vollständig einschließlich signiertem
iPhone-/iPad-Paket 208, Artefakt 13789192915; Upload false. Der automatische
Push-Lauf und der manuelle Lauf sind unterschiedliche Auslöser. Das signierte
208 enthält den Bankimport und Offline-Konfliktfix, die spätere Personal-
Korrektur jedoch noch nicht. Keine neue Live- oder Geräteinstallation.
