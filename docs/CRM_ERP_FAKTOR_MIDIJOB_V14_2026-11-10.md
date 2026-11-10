# Faktor und Midijob: additive Vertragsarbeit V14

Stand10.11.2026. Gesamtziel bleibt vollständig erhalten. Arbeitskopie
`/workspace/smartplan-factor-transition-20261110`, Branch
`codex/factor-transition-20261110`, Basis a40fc56. Die neue API und beide Clients sind lokal implementiert und
gezielt geprüft. Die vollständige aktuelle Appprüfung besteht1961 Fälle ohne
Fehler/Skip; Paketprüfung ist abgeschlossen. Der vollständige Backendlauf ist
noch aktiv. Testbranch-Kandidat; keine Serverinstallation oder fachliche Freigabe.

## Beobachtete offene Funktion

Das vorhandene Faktorprofil ist auch bei ausdrücklich belegtem niedrigerem
regelmäßigem Jahresentgelt strukturell gültig; die bisherigen Rechenversionen
geben ohne ihre eigene Übergangsbereichsprognose aber ausdrücklich kein Netto
aus. Ein tatsächlich ausgeführter2000-Euro-Faktorfall bestätigt diese Sperre.
Die alten Faktorprofile und alle historischen Rechenkerne bleiben unverändert.

## Implementierter enger erster Umfang

Genau ein unveränderter voller deutscher Steuer-/SV-Monat2026, ein reguläres
Faktorprofil KlasseIV mit tatsächlichem ELStAM-Faktor, ein Monatsvertrag und eine
vollständige vor Monatsbeginn belegte Zwölfmonatsprognose zwischen603,01 und
2000Euro. Keine neue automatische Statuswahl aus dem tatsächlich niedrigen
Entgelt. Andere Versicherungs-/Alters-/Sonderfälle, Einmalbezüge, Reisen, P4-
Ansprüche und untermonatige Wechsel bleiben für diesen neuen Vertrag gesperrt.

Die Prognose ist am neuen privaten Gesamtfall mit tatsächlichem Original,
Person und Gültigkeitszeitraum gebunden. Das ursprüngliche Faktorprofil
erhält keine erfundenen nachträglichen Felder. Eine ausdrücklich bezeichnete
Beitragsprojektion entfernt ausschließlich den dortigen Faktor aus der
Steuerkomponente und ergänzt die separat belegte Prognose; sie wird nur vom
unveränderten V3-Beitragskern ausgewertet. Die eigentliche Steuer verwendet
den unveränderten Faktor-PAP und tatsächliches Brutto. Beide Projektionen,
Originale, Regelversionen und Quellen werden vollständig gebunden.

## Konkreter Ablauf

1. Neue reine Version mit strengen Eingaben, alten Beitragssätzen/Formeln und
   unabhängig aus dem gepinnten PAP-XML ausgeführten Java-Steuerreferenzen.
2. Eigener vollständiger Gesamtfall-/Quellenvertrag, keine stillschweigende
   Freigabe oder Übernahme bereits verwendeter Altfälle.
3. Browser und native App mit expliziter Prognose, Vorschau, Bestätigung,
   aktueller Fähigkeits-/Rechteprüfung und unverändertem Wiederholungsauftrag.
4. Private PDF-/Lohnkonto-/Zahlungs-/EÜR-/Jahreskette und Korrekturen ohne
   Umschreiben alter Originale oder tatsächlich gezahlter Beträge.
5. Tatsächliche MFA-/PostgreSQL-/Parallelitäts-/CRLF-/vollständige Restore-
   und Client-/Paketprüfungen. Erst dann Veröffentlichung auf dem autorisierten
   Testbranch; die derzeitige signierte iPhone-Vorbereitung nicht abbrechen.

## Gelesene aktuelle Primärquellen

[§39f EStG](https://www.gesetze-im-internet.de/estg/__39f.html), insbesondere
Absatz2/4: Arbeitgeber verwendet KlasseIV und den gebildeten Faktor; dieser
gehört in den maschinellen PAP. Der Haushaltsfaktor wird nicht selbst berechnet.
[§20 SGBIV](https://www.gesetze-im-internet.de/sgb_4/__20.html) und
[DRV2026-Übergangsbereich](https://www.deutsche-rentenversicherung.de/DRV/DE/Experten/Arbeitgeber-und-Steuerberater/summa-summarum/Lexikon/U/uebergangsbereich.html)
beschreiben getrennte Beitragsbasen und die2026-Werte603/2000 sowie0,6619.
Beide Normen und die DRV-Seite wurden am10.11. tatsächlich über den öffentlichen
Webzugang vollständig im einschlägigen Abschnitt gelesen. Die neun veröffentlichten
DRV-Basen dienen als unabhängige Beitragsreferenz. Für die Steuer werden eigene
kontrollierte Monatsfälle aus dem vorhandenen gepinnten XML erzeugt; ein neuer
direkter amtlicher XML-Download oder eine Systemzulassung wird nicht behauptet.


## Tatsächliche aktuelle Prüfung und Korrekturen

Die reine Version de_2026_factor_transition_month_v14 und Quellenvertrag6
verwenden den unveränderten V3-Beitragskern und den Faktor-PAP des V9-Monats.
32 unabhängige Java-Ausführungen des gepinnten XML und neun DRV-Beitragsbasen
sind tatsächlich geprüft. Originalprofile erhalten keine zusätzlichen Felder;
Beitragsprojektion und ursprüngliche Steuerparameter werden unabhängig gebunden.

Die ursprüngliche fehlende API-Unterstützung, die anfangs unnötig geforderte
neuere Identitätsschemafassung und zwei Widget-Timer-Aufbaufehler bleiben in den
Rohdaten erhalten. Vollständige explizite historische ELStAM-Identitäten sind
jetzt ohne Umschreiben ihrer Fassung lesbar. Nach gezielter Lebenszyklus-
korrektur des Tests bestehen alle acht neuen nativen Fälle einschließlich des
wirklichen vollständig ausgefüllten Formulars. Die gesamte Appanalyse ist
sauber (12,4s); die vollständige aktuelle App-Suite besteht inzwischen1961 Fälle ohne Fehler/Skip.

1077 Browser-Vertragstests bestehen ohne Fehler/Skip. Der erste Gesamtmodullauf
besteht1076 Fälle und scheitert allein beim Zeitzonen-Unterprozess mit Sandbox-
EPERM; der unveränderte Lauf mit den nötigen lokalen Prozessrechten besteht
alle1077. Sechs neue V14-Vertragstests und der tatsächliche isolierte Chromium-
Ablauf prüfen originale Auswahl, unabhängige Prognose, positive Faktorsteuer,
zwei unveränderte Wiederholungen nach verlorenem HTTP-Ergebnis, unveränderte
Projektzeiten, private PDF sowie echte Mitarbeiteranmeldung/Beleganzeige,
PDF-/JSON-Download, Rohdatenverweigerung,390px und frischen Rechtewiderruf.

Der wirkliche PostgreSQL-Fall besteht in54,205s (Runner55,357s): konkurrierende
Gesamtfall- und Lohnschreiber, unverändertes Faktororiginal, reduzierte
Beitragsbasen854,06/568,36 bei1000Euro Monatsbrutto, Netto874,67, tatsächliche
Zahlung, EÜR874,67 ohne Vorsteuer, Jahresbasis1000Euro, eigener reduzierter
Mitarbeiterbeleg, vollständiger Dump-Restore, identische Original-PDF und
Annahmequittungen sowie401 der alten Sitzung und erneute tatsächliche MFA.
Der erste PG-Aufbau benutzte versehentlich das2000-Euro-Jahresprofil zu einer
1000-Euro-Prognose. Die bestehende echte400-Sperre wurde unabhängig reproduziert;
nur das kontrollierte Profil wurde vor seiner Erstellung passend belegt.
Produktprüfung blieb unverändert. Beide eigenen Container sind nach voller
ID/Label/Loopbackprüfung entfernt; fremde Container bleiben unverändert.

Ein zusätzlicher wirklicher Korrekturfall besteht in1,847s: nachträglicher
Prüfvermerk mit eigener Gesamtfall-/Lohnrevision, unveränderte ursprüngliche
Fassungen, PDFs und wiederholte Annahmequittungen. Kein automatischer Wechsel
bestehender anderer Gesamtfallverträge und keine Übernahme bereits verwendeter
Altfälle inV14. Zusätzliche Bezüge oder Statuswechsel benötigen einen weiteren
explizit geprüften Vertrag.

## Gefundene Mitarbeiterbeleg-Leserlücke beider Clients

Der unveränderte produktive Projektor erzeugt für Source3 bereits reduzierte
Schema2-Belege. Beide Clientleser ließen dafür bisher ausschließlich V5 zu und
lehnten die echten V10-/V11-/V12-/V13-Belege sowie den neuen V14 ab. Elf aus
wirklichen synthetischen API-Läufen mit dem unveränderten Projektor und PDF-
Renderer erzeugte Belege zeigen die Lücke tatsächlich rot. Kein historischer
Backend-Beleg, keine Rechenversion und kein ursprüngliches PDF wird verändert.

Beide Leser akzeptieren jetzt nur die ausdrücklich bekannten exakten Regel-/
Umfangspaare unter unverändertem Strukturschema2. Unbekannte Versionen und
vertauschte bekannte Kombinationen bleiben auch mit neu gebildetem Belegsha
abgewiesen.17 gemeinsame Browser- und18 Appfälle prüfen die elf tatsächlichen
JSON-/PDF-Originale, Privatsphäre, fremde Personen, manipulierte Dateien und
mobile eigene Beleganzeige mit Rechtewiderruf. Die neue echte V14-Browser-
Mitarbeiteranmeldung ist zusätzlich durchgeführt; ein gebautes Gerät ersetzt
sie nicht. Der Projektor bleibt bytegleich und eine eigene Gegenprobe erzeugt
sämtliche elf Datensätze exakt erneut.

Die aktuelle App-/Paketprüfung ist abgeschlossen. Die vollständige Backend-
Schlussmeldung, eigene Remoteprüfung und Gesamtziel-Abnahmen fehlen noch. Keine Prozent- oder Gesamtfreigabe aus diesen
abgegrenzten Erfolgen ableiten. Nachweise werden in
[evidence/factor-transition-2026-11-10/manifest.json](evidence/factor-transition-2026-11-10/manifest.json)
gesichert; frühere Fehlläufe bleiben von späteren Erfolgen getrennt.

58 gemeinsame neue/alte Backend-, Belegprojektions-, CI- und Paketfälle bestehen
in61,686s. Der anschließende tatsächliche vollständige App-Lauf besteht1961 sichtbare
Fälle ohne Fehler/Skip und bleibt als eigener Nachweis getrennt.


## Vollständige aktuelle Appprüfung und getrennte Auslieferung

Der integrierte Stand13b9092 besteht1961 sichtbare Appfälle ohne Fehler und
Skip.260 verborgene Ladeeinträge werden ausdrücklich nicht mitgezählt. Die
wirkliche success:true-Schlussmeldung steht bei1437145ms; Runnerexit0 nach
1446,014s. App-/Backenddateien sind seit Start bytegleich. Nachträglich geändert
sind ausschließlich Dokumentation, der separat geprüfte iPhone-Workflowguard
und die unten beschriebene Browser-Datumsanzeige. Der vollständige Backendlauf
mit2133 entdeckten Fällen ist noch aktiv und wird nicht als bestanden gezählt.
Die153-Komponenten-Inventarausgabe ist exakt mit der eingecheckten identisch.

Die tatsächliche mobile Sichtprüfung zeigt einen bestehenden Callbackfehler:
map übergibt den Arrayindex als zweiten formatDate-Parameter und erzeugt dadurch
für reine Lohndaten ab dem zweiten Tag eine erfundene12:00-Uhrzeit. Ausschließlich
der Callback ist jetzt einstellig. Formatierer und Lohndaten bleiben unverändert.
17 gezielte Vertragsfälle und der erneute tatsächliche MFA-/Mitarbeiter-/PDF-/
JSON-/Widerrufsablauf bestehen; die neue Datumszelle enthält keine Uhrzeit.
Beide echten Bilder und vollständige synthetische Befehlsprotokolle bleiben
getrennt erhalten; die Korrektur ist auch tatsächlich visuell geprüft.

Die echte Keychain-Gegenprobe42806142665 an40d8fcf ist abgeschlossen: beide Jobs
bestehen, privater Erstexport und endgültiger Apple-Export gelingen, finale
Signatur-/Team-/Berechtigungsprüfung besteht, Schlüsselbereinigung besteht.
Signiertes Artefakt Smartplan-Office-iOS-198:13762109533,29866901Bytes.
TestFlight-Upload ist ausdrücklichskipped; keine Geräteabnahme. Dieses Artefakt
beweist den reparierten Auslieferungsweg, enthält jedoch noch nicht den neuen
V14-Client. Der unabhängige Development-Lauf42806104268 besteht alle20 Gruppen.
Die neue tatsächlich rot/grün geprüfte Gruppenwahl trennt normale Quellprüfungen
von ausdrücklich signierten Läufen und verhindert ihren Abbruch durch einen
normalen Push.12 gezielte Auslieferungsfälle bestehen2,368s, YAML/22 Shellblöcke
bestehen. Die48 tatsächlichen Auswahlkombinationen und der Uploadguard bleiben
erhalten. Der bereits abgeschlossene echte Signierlauf wird nicht nachträglich
als Prüfung dieses zusätzlichen lokalen Workflowguards ausgegeben.

Der zusätzliche öffentliche Serverabruf liefert403 durchEnvoy. Die beobachtete
Cloud-Zulassungsliste ist eingeschränkt und enthält office.smartplan-hofmann.de
nicht. Damit ist der tatsächliche Ursprungserver nicht neu bestätigt. Keine
Anmeldung, keine private Abfrage und keine Installation. Der zuletzt vom Nutzer
bestätigte Quellstand bleibt a93cb4d vom05.11.; aus dem Cloudfehler wird kein
Serverausfall abgeleitet. Das aktuelle Gesamtziel ist weiterhin offen.


Nachlauf12:32UTC: vollständiger Backend-Lauf2133 Fälle,2130 erfolgreich,
drei erläuterte Auslassungen, keine Fehler,2757,214s. App-/Backendruntime
bleibt bytegleich zum vollständigen Prüfstand13b9092. Kandidat91fa18b ist
veröffentlicht und Remote-Zeiger bestätigt. Eigene neue Remoteprüfung läuft.
