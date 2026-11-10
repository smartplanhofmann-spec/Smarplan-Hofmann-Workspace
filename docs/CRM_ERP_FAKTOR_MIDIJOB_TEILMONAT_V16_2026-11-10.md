# Faktor und Midijob bei belegtem Eintritt oder Austritt

Aktive Entwicklung auf `codex/factor-transition-periods-20261110`, Basis
13c6663. Der veröffentlichte Produktstand 29b02c8 und seine tatsächlich
erfolgreichen 20 Prüfgruppen, Windows-Pakete und signierte iPhone-Vorbereitung
210 bleiben davon getrennt. Produktquelle4aa0abd ist veröffentlicht und besteht alle20eigenen
Development-Gruppen, Windows-Paketierung, automatischen iPhone-Release211 und
tatsächliche signierte iPhone-Vorbereitung212. TestFlight-Upload bleibt false. Originalziel und historische Rechenversionen bleiben erhalten.

## Tatsächliche verbleibende Funktion

V14 verarbeitet ausschließlich den vollständigen Faktor-/Midijob-Monat.
Der Faktor-Periodenvertrag V9 verarbeitet den gewöhnlichen Teilmonat, verlangt
bei niedrigerem regelmäßigem Entgelt aber einen eigenen belegten
Übergangsbereichsvertrag. Ein Eintritt oder Austritt innerhalb des Monats
darf durch Umbenennen eines Vollmonatsfalls nicht berechenbar werden.

Der vermeintlich offene erneute Nettoausgleich nach V4 ist dagegen bereits
als V5 implementiert und mit beiden Clients sowie PostgreSQL/Restore geprüft.
Der entsprechende alte Restvermerk wird mit dem tatsächlichen
[V5-Nachweis](CRM_ERP_SOURCE5_NETTOAUSGLEICHE_V5_2026-11-10.md) abgeglichen;
die Funktion wird nicht noch einmal implementiert.

## Begrenzter erster V16-Vertrag

- Genau eine belegte Beschäftigungsepisode mit Eintritt oder Austritt im
  deutschen Kalendermonat 2026, ein fester Monatsvertrag mit ausdrücklich
  belegter Vertragsmethode `contractual_30_days` und ein unverändertes
  wirksames Klasse-IV-Faktorprofil.
- Tatsächliches Teilentgelt, Steuer-/SV-Tage und Teil-BBG aus dem ursprünglichen
  V9-Periodenfall. Keine hinzugefügten Arbeitsstunden oder angenommenen Tage.
- Separate vollständige Zwölfmonatsprognose zwischen 603,01 und 2.000 Euro
  regelmäßigem Monatsentgelt, eigenes privates Original und ausdrückliche
  Prüfung von Alleinbeschäftigung, festem Monatsvertrag und Teilentgeltmethode.
  Die Prognose wird nicht in ein historisches Faktorprofil hineingeschrieben.
- Unveränderte tägliche Faktor-PAP-Komponente aus V9 und unveränderte
  Beitrags-/Pflege-/Rundungsbausteine. Die Bruttokürzung und die SV-Zeitachse
  werden ausdrücklich gebunden. Keine Übernahme von Reisen, P4-Ansprüchen,
  Einmalzahlungen, mehreren Profilen, Versicherungswechseln oder anderen
  zusätzlichen Sonderfällen durch eine allgemeine Freigabeflagge.
- Eigene Regel `de_2026_factor_transition_period_v16`, Quellenvertrag 7,
  Umfang `regular_transition_factor_period` und Fähigkeit
  `payroll_factor_transition_periods`. Alte V9-/V14-Originale bleiben unter
  ihren bisherigen Regeln lesbar und berechenbar.

## Bereits unmittelbar gelesene Primärquellen

[DRV-GRA §20, Abschnitt „Beitragspflichtige Einnahmen in Teilmonaten“](https://rvrecht.deutsche-rentenversicherung.de/SharedDocs/rvRecht/01_GRA_SGB/04_SGB_IV/pp_0001_25/gra_sgb004_p_0020.html),
[gemeinsames Rundschreiben vom 20.12.2022, insbesondere 4.3.2.5 und Beispiel 7b](https://www.deutsche-rentenversicherung.de/SharedDocs/Downloads/DE/Fachliteratur_Kommentare_Gesetzestexte/summa_summarum/rundschreiben/2022/beschaeftigungen_im_uebergangsbereich_20_12_2022.pdf?__blob=publicationFile&v=3)
und [DRV-Formeln 2026](https://www.deutsche-rentenversicherung.de/DRV/DE/Experten/Arbeitgeber-und-Steuerberater/summa-summarum/Lexikon/U/uebergangsbereich)
sind am 10.11. im einschlägigen Abschnitt direkt gelesen. Das Rundschreiben
unterscheidet ausdrücklich abweichende arbeits-/tarifvertragliche
Teilentgeltmethoden; daraus wird keine pauschale Fehlerbehauptung über andere
vorhandene Vertragsmethoden abgeleitet. Der neue erste Vertrag beschränkt
sich ausdrücklich auf die belegte 30-Tage-Methode. Für die Faktorsteuer
werden unabhängige Ausführungen der bereits fest gehashten PAP-XML verwendet;
ein neuer amtlicher XML-Download oder eine Systemzulassung wird nicht behauptet.

## Erforderlicher gemeinsamer Nachweis

Unabhängige XML-Steuerwerte und rationale Beitragsgegenwerte, echte neue
Teilmonats-/Quellen-/Vorschau-/Laufwege, unveränderte alte Vollmonatsgrenzen,
private PDF und Mitarbeiterbelege, belegte Zahlung/EÜR/Jahresbasis, beide
Clients samt verlorener Antwort und frischem Rechteentzug, tatsächliche
PostgreSQL-Konkurrenz und vollständiger Restore, Paketierung und gemeinsame
Regression. Ergebnisse werden erst nach tatsächlichem Lauf eingetragen.
Keine Meldung, Überweisung, echte Nachricht, Serverinstallation oder
TestFlight-Veröffentlichung wird durch diesen neuen Rechenvertrag ausgelöst.

## Abschließender technischer Nachweis

Eigene Development-Prüfung42898771085: alle20Gruppen erfolgreich.
2.199Backendfälle in1.611,192s mit3ausgewiesenen Auslassungen; Linux-App2.020
Hauptfälle plus3native PDF-Fälle, insgesamt2.023. Windows1.975App- und81portable
Backendfälle samt tatsächlicher Paketierung. Eigener tatsächlicher PG-/MFA-/
Konkurrenz-/Cash-/EÜR-/Jahres-/CRLF-/Restoreweg und neuer sowie alter echter
Browserablauf erfolgreich. Der separat entpackte feste Commit4aa0abd besteht
MFA, neue Fähigkeit, vier Browserdateien, wirklichen Fall/Lauf/PDF und Retry.

Der vollständige lokale App-Lauf besteht mit2.023Fällen in25:11. Der zusätzliche
lokale Backendaufruf hatte wegen des fehlenden Projektverzeichnisses im
Pythonpfad4Importfehler unter2.178erfassten Fällen. Die betroffenen4Module und
der später ergänzte Austrittsfall bestehen mit25Fällen im korrigierten Nachlauf.
2.178−4Platzhalter+25tatsächliche Fälle ergeben2.199verschiedene ausgewählte
Fälle; der erste rote Aufruf bleibt rot. Der eigene vollständige CI-Lauf ist
davon getrennt erfolgreich. Der ältere Node-Sandboxfehler und alle weiteren
Erstbefunde bleiben ebenfalls als unveränderte Rohbelege erhalten.

Automatischer iPhone-Release211 und manuelle Vorbereitung42898966618 mit
signiertem Paket212 erfolgreich. Mac-Vorprüfung:2.015Hauptfälle plus3native PDF-
Fälle;5Linux-Integrationsfälle ausdrücklich ausgelassen und separat bestanden.
Endgültige Apple-Distributionssignatur, Team und Keychain-Berechtigung sowie
Schlüsselbereinigung bestätigt. Tatsächlicher TestFlight-Schritt ausgelassen.
Die konkreten [Pakete und Prüfsummen](CRM_ERP_LIEFERSTAND_AKTUELL.md),
[Serveranleitung](CRM_ERP_SERVERUPDATE_4AA0ABD_2026-11-10.md) und das
[Manifest](evidence/factor-transition-periods-2026-11-10/manifest.json)
binden diese unterschiedlichen Zustände. Keine neue Liveinstallation, reale
Geräteprüfung oder unabhängige Fachfreigabe wird daraus abgeleitet.

## Erhaltener lokaler Zwischenstand vor der Veröffentlichung

Der neue Quellenvertrag 7 ist additiv im Backend, Browser, nativen Client und
kanonischen Windows-Quelleninventar eingebunden. Der Browser und die App führen
unter Personal → Personalakte → Lohnberechnung 2026 → Abrechnungsfälle den
Eintrag **Midijob-Teilmonat mit belegtem ELStAM-Faktor**. Die ursprünglichen
Perioden-, Vertrags-, Faktor-, Identitäts- und privaten Prognoseoriginale
müssen ausdrücklich ausgewählt werden. Alleinbeschäftigung, fester Vertrag,
30-Tage-Methode und vollständige Prognose brauchen eigene Bestätigungen.

Die getrennt angenommene Fallvorschau bindet bereits die vollständige
Finanzkomponente. Ein nachträglich geänderter Steuerbetrag wird auch mit
neu berechnetem Laufhash abgewiesen, wenn er diesem angenommenen Fall
widerspricht. Die native gemeinsame Vorschauprüfung verwendete für V14 ein
in der Vorschauantwort nicht vorhandenes `rule_version`-Feld. Ein absichtlich
veränderter Vorschauhash hat die Lücke reproduziert; der Leser verwendet jetzt
die ausdrücklich angeforderte Version. V14 und V16 werden gemeinsam geprüft.
Historische Rechenregeln und gespeicherte Originale sind davon nicht verändert.

Bisher tatsächlich erfolgreich:

- 300 getrennte Java-Ausführungen der fest gehashten PAP-XML plus eigenständige
  rationale Beitragsrechnung; keine Produktion des Lohnkerns in der Referenz.
- 24 gemeinsame neue und alte Backendfälle, darunter die 300 Gegenwerte,
  Februar, tatsächlicher Austritt, der 31. Tag und ein 30-Tage-Teilmonat;
  weitere tatsächliche Austritts-API-Prüfung mit unverändertem früherem Original.
- Neuer tatsächlicher MFA-/HTTP-Browserablauf mit ausgewählten Originalen,
  zwei verlorenen Speicherantworten, identischer Wiederholung, privatem PDF,
  eigenem Mitarbeiter-JSON/PDF, Rechteentzug und 390-Pixel-Ansicht. Der bisherige
  V14-Vollmonatsablauf besteht erneut.
- 26 gemeinsame V14-/V16-Appfälle; anschließend 19 aktuelle V16-Fälle mit
  tatsächlichem Formular bei 390 und 1.100 Pixel Breite. Analyse ohne Befund.
- 11 neue Browserverträge einschließlich unveränderter Wiederholung bei
  entzogenem Feature/Fachrecht und eigenem Mitarbeiterbeleg. Der erste
  gemeinsame Nachlauf mit 1.106 Verträgen besteht; der erweiterte Lauf enthält
  1.109. Sein erster Versuch scheitert ausschließlich beim Start eines
  Zeitzonen-Unterprozesses an Sandbox-EPERM; der erneute Lauf mit den nötigen
  Prozessrechten wird separat ausgewiesen.
- Tatsächliche PostgreSQL-/MFA-/Konkurrenz-/Zahlungs-/EÜR-/Jahres-/CRLF-/
  Komplettrestorekette, ein Test in57,818s. Eigener markierter Loopbackcontainer
  anschließend anhand seiner exakten ID, Markierung und Portbindung entfernt.
- 30 Paket-, CI-Auswahl- und Archivfälle. Ihre vor dem neuen lokalen Commit
  eingefrorenen Archivtests betreffen ausdrücklich noch den alten HEAD;
  der neue eingefrorene Quellstand erhält einen eigenen Nachlauf.

Der positive Teilmonatsbeleg für einen Monatsvertrag von2.000EUR und Eintritt
am15.10. enthält1.133,33EUR Brutto,37,40EUR Lohnsteuer,246,49EUR Arbeitnehmer-
beiträge und849,44EUR Netto. Die belegte tatsächliche Zahlung wird einmal in
Cash/EÜR übernommen; die Jahresbasis enthält17SV-Tage. Dies sind kontrollierte
synthetische Fälle und keine echte Lohnabrechnung oder Überweisung.

Die unveränderten Rohbelege einschließlich gescheiterter erster Versuche stehen
unter [evidence/factor-transition-periods-2026-11-10](evidence/factor-transition-periods-2026-11-10/).
Die vollständigen lokalen App-/Backendläufe sind beim Anlegen dieses Nachweises
noch aktiv. Eigene neue CI, Windows-/iPhone-Pakete, Serverinstallation und reale
Geräte-/Fachabnahme sind getrennte noch nicht behauptete Zustände.
