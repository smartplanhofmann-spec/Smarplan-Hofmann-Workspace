# Verbindlicher aktueller Arbeitsstand

Stand: 10.11.2026. Der Auftrag bleibt die vollständige CRM-/ERP-Software gemäß
Nutzerauftrag und unveränderter `CRM_ERP_Gesamtziel.txt`. Eine abgeschlossene
Etappe verkleinert das Gesamtziel nicht und beendet den Auftrag nicht.

## Projekt und verbindliche Quellen

- Hauptprojekt: `/workspace/Smarplan-Hofmann-Workspace`, Branch
  `codex/finish-20261108`.
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

## Quellcode, Prüfstand und Installation sind getrennt

| Stand | Tatsächlich bestätigt |
|---|---|
| Aktuell veröffentlichter Quell- und Testbranch | `ca14af3822aac0706c2acf80bdb568cc5f29afbb`, veröffentlicht und Remote-Zeiger bestätigt. V14 und Qonto-Leseansicht mit beiden Clients enthalten. Eigenkonto-Key67b99d3 liegt geprüft lokal für die nächste Integration vor. |
| Eigene aktuelle Workflowprüfung | An91fa18b: Development42814265700 alle20 Gruppen erfolgreich, unsignierter iPhone42814265712 erfolgreich. Mailbot42814265743 erfolgreich, kein echter Versand. Manueller signierter Vorbereitungslauf42816832390 an91fa: unsigniert erfolgreich; erster Apple-Export scheitert am Netzwerk und fehlendem Profil nach diesem Abbruch. Rohfehler erhalten; genau der gescheiterte Job wurde mit identischem Quellstand wiederholt, neuer Signierjob129852986325 läuft, Uploadfalse. Neue ca14-Prüfung42821768166 läuft separat, Mailbot42821768083 erfolgreich. Vorläuferfehler bleiben historisch erhalten. |
| Vollständige CI zum Installationsprodukt c4a2d8f | Development42790149143:alle20 Gruppen erfolgreich. Die anHTTP403 vor Testbeginn gescheiterte Gruppe wurde allein wiederholt; alle13 wirklichen Browserabläufe bestehen, Erstfehler erhalten. Unsignierter iPhone42790149399 erfolgreich, signierter Upload übersprungen. Mailbot-Verträge42790149124 auf Linux/Windows erfolgreich; kein echter Versand. |
| Aktueller geprüfter veröffentlichter Reparaturstand | `40d8fcf5571e8edc898e2e20b1cf7fe36e52149e`: alle20 Development-Gruppen42806104268 erfolgreich. Eigener manueller iPhone42806142665: vollständiger unsignierter Client, endgültiges signiertes IPA, strenge Keychain-/Teamprüfung und Schlüsselbereinigung erfolgreich. Signiertes Artefakt198 vorhanden; TestFlight-Uploadskipped. V14 ist davon getrennt. |
| Letzter vom Nutzer bestätigter Server | `a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5` vom05.11.; drei Dienste/Sicherungstimer und kontrollierter Updateabschluss bestätigt. Der10.11.-GET auf/ready liefert403 durchEnvoy; die tatsächliche Cloud-Zulassungsliste enthält die Domain nicht. Kein neuer bestätigter Ursprungstand und kein Update. |
| Geräte-/Fach-/Gesamtabnahme | Keine neue echte Windows-/iPhone- oder externe Fach-/Sicherheitsfreigabe aus Cloudtests ableiten. |

Das tatsächliche [Windows-Online-Paket c4a2d8f](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42790149143/artifacts/13752796971)
ist gebaut (22183211Bytes). Ein unsignierter iPhone-Build ist keine installierbare
signierte Verteilung. Die Backendkennung0.12.0-online-pilot ist eine API-
Kompatibilitätskennung, keine App-/Paketversion.

## Aktive Arbeit: signiertes iPhone-Paket getrennt vom Upload

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


## Tatsächlicher iPhone-Nachlauf erfolgreich

[Signiertes Paket200](CRM_ERP_IPHONE_SIGNIERTES_PAKET_200_2026-11-10.md) an91fa18b:
Wiederholungsjob129852986325 erfolgreich, beide Apple-Exporte, strenge finale
Signatur-/Team-/Keychain-Prüfung und Bereinigung bestehen. Artefakt13769975157
mit29898645Bytes vorhanden; TestFlight-Uploadskipped. V14 enthalten, Qonto noch
nicht enthalten. Der tatsächliche erste Netzwerkfehler bleibt erhalten.
Keine neue Geräteinstallation oder Serveraktualisierung daraus ableiten.
