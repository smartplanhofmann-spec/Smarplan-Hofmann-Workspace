# Integrationsstand vom 03.11.2026

Entwicklungsstand, keine Produktivfreigabe. Projekt:
`/workspace/Smarplan-Hofmann-Workspace`, Branch `work`.
Das vollständige Gesamtziel und die Abnahmen A–G bleiben bestehen.

Aktueller gemeinsamer Nachweis: **Anfangssalden und Katalogoriginale auf Source4**
mit 1.565 bestandenen Backend-, 522 Node- und 1.118 Fluttertests sowie 16
Paketprüfungen. [Prüfumfang, tatsächliche Restore-/Browserabläufe und Grenzen](CRM_ERP_ANFANGSSALDEN_KATALOG_GESAMTPRUEFUNG_2026-11-04.md).
Source5, historische Anlagen und datierte Katalogpreise laufen getrennt weiter.

## Bestätigte Geschäftsgrundlagen

Einzelunternehmen mit EÜR, Regelbesteuerung, Ist-Versteuerung, 19 % Standard-USt,
SKR04 und Nettopreise. Beschäftigungsumfang: reguläre Mitarbeiter und Minijobs.
Steuerlicher Gültigkeits- und Buchführungsbeginn werden pro Unternehmen erfasst,
nicht aus dem Datum erfunden. Siehe `CRM_ERP_ENTSCHEIDUNGEN.md`.

`CRM_ERP_Gesamtziel.txt` bleibt unverändert zum Upload, SHA-256:
`a4dea28f6de4afd3e36d1549441aad91ce16dad374f56097979cc2d79b07fbf5`.

## Umgesetzt und abgegrenzt geprüft

| Bereich | Durchgängiger Stand | Nachweis |
| --- | --- | --- |
| Projektwirtschaftlichkeit | Originalbeleg → Prüfung → Kostenarten → Plan/Ist → getrennte Erlöse/Zahlungen → Historie | Domain, PostgreSQL, Flutter/HTTP und Chromium; `CRM_ERP_PROJEKTWIRTSCHAFTLICHKEIT_CLIENTS.md` |
| Geräteherkunft | Original-Lieferschein → Wareneingang/Entnahme → Gerät → Wartungshistorie | Domain, HTTP, PostgreSQL/Restore, beide Clients; `CRM_ERP_GERAETEHERKUNFT.md` |
| Kundenarbeitsbereich | Eigener Zugang → freigegebene Infos/Originale → Kundenupload → Prüfung/Übernahme → Widerruf | Domain/HTTP, PostgreSQL/Restore, Flutter und Chromium; `CRM_ERP_KUNDENARBEITSBEREICH.md` |
| Personal | Originalakte/Entgeltvereinbarung → Auslage → Fremdfreigabe → Erstattung/Rückzahlung → Monatsvorbereitung | 14 Domain- und 2 PostgreSQL-/MFA-/HTTP-/Restore-Fälle, beide Clients; `CRM_ERP_PERSONAL_WORKFLOW.md` |
| EÜR | Geldfluss/Original → steuerliche Einordnung → Journal → Korrektur/Gegenbuchung → Perioden → Jahresprüfpaket | Fach-, PostgreSQL-/MFA-/Restore- und Clientprüfungen; `CRM_ERP_EUER_WORKFLOW_PRUEFUNG.md`, `CRM_ERP_EUER_CLIENTS.md` |
| Rechnungsketten | Abschlag → kumulierte Rechnung → Schlussrechnung → Ursprungsbindung/Rücknahme/Wiederbelegung → EÜR | 9 neue Fachfälle, 107 Regressionen, 2 PostgreSQL-/Restore-Fälle, 30 Flutterfälle, Chromium; `CRM_ERP_EUER_KETTEN_ANALYSE.md` |
| Lohnrechnung 2026 | Private Profile → Minijob oder begrenzter regulärer Monatsfall → Netto → Korrektur → historische PDF/JSON | 43 Fach-/Rechentests inklusive 258 amtlicher PAP-Referenzwerte, 6 PostgreSQL-/MFA-/Restore-Fälle, beide Clients; `CRM_ERP_LOHN_RECHENWERK_2026.md` |
| Assistent/Regeln | Quellen → Plan → Automatik/Freigabe/Verbot → Fachaktion → Quittung | 27 Fach-/Provider-/HTTP-Fälle, 4 PostgreSQL-/MFA-/Versand-/Restore-Fälle, 8 Flutter-, 10 Node-Fälle, Zwei-Benutzer-Chromium; `CRM_ERP_ASSISTENT.md`, `CRM_ERP_ASSISTENT_CLIENTS.md` |
| Inventur | Lager-/Artikelstand → Zählung → Differenzgrund/Bewertung → Freigabe → Bestand → historische Korrektur | 44 Domain-/Lager-/HTTP-Fälle, PostgreSQL/Restore, 6 Node-, 4 Flutterfälle, Chromium; `CRM_ERP_INVENTUR.md` |
| Unternehmensübersicht | Aufgaben/Termine → Erlöse/Kosten/Zahlungen → Projektquellen/EÜR | 8 Domain-/HTTP-, 3 Node-, 3 Flutterfälle plus Sitzungs-/Shellregression, Chromium; `CRM_ERP_UNTERNEHMENSUEBERSICHT.md` |

Testzahlen überschneiden sich teilweise und dürfen nicht zu einer scheinbaren
Gesamtzahl oder einem Fertigstellungsprozentsatz addiert werden.

Weitere abgeschlossene Teilabläufe:

| Bereich | Aktueller Nachweis |
| --- | --- |
| Vertriebschancen | 11 Fachfälle, 2 PostgreSQL-/MFA-/Restore-Fälle, 5 Node-, 6 Flutterfälle, echter Browser; `CRM_ERP_VERTRIEB.md` |
| Lohnkonten und Jahresausgabe | Pflichtstammdaten, tatsächliche Zahlungsteile, belegte Vorträge und Korrekturen; im oben genannten Lohnkern enthalten, 35 Node-/34 Flutterfälle und Browser; `CRM_ERP_LOHN_CLIENTS.md` |
| Sprachentwurf | 20 neue Backend-/HTTP-/PostgreSQL-Fälle, 16 kombinierte Flutter-/17 Node-Fälle und echte Browseraufnahme mit synthetischem Mikrofon; `CRM_ERP_SPRACHE.md` |
| Unternehmensübergabe | 14 Fach-, 2 HTTP-, 2 PostgreSQL-/Restore-Fälle, 12 Node-/9 Flutterfälle mit gemeinsamen Regressionen, tatsächliches ZIP und ausgelieferter Prüfer im Browserablauf; `CRM_ERP_UNTERNEHMENSEXPORT.md` |
| Dateiimport | 14 Fach-, 2 lokale HTTP-, 2 PostgreSQL-Fälle, je 6 Node-/Flutterfälle, Browser einschließlich Originaldownload und Zielnavigation; `CRM_ERP_DATEIMIGRATION.md`, `CRM_ERP_DATEIIMPORT.md` |
| Freie Felder | 11 Fachfälle plus 28 Foundation-Regressionen, 2 PostgreSQL-/Restore-, 6 Node-/7 Flutterfälle, Browser mit fünf Feldtypen und drei Entitäten; `CRM_ERP_ZUSATZFELDER.md` |
| Datenschutzfälle | 19 Fach-/MFA-/HTTP-Fälle, tatsächlicher PostgreSQL-/Altbackup-Restore, 8 Node-/9 Flutterfälle, Browser; frische Quellen, begrenzte Exporte, Berichtigung und Wiederherstellungssperren; `CRM_ERP_DATENSCHUTZFAELLE.md` |
| Lohnzahlungen → EÜR | 9 Fach-, 2 HTTP-, 3 PostgreSQL-Fälle, 20 Node-/17 Flutterfälle, Browser einschließlich Buchhalter ohne Personalrecht; tatsächliche Zahlungen und Abführungen, aggregierte Finanzquelle; `CRM_ERP_LOHNZAHLUNGEN_EUER_CLIENTS.md` |
| Kundenservice | 9 Fach-, 2 PostgreSQL-Fälle, 19 kombinierte Node-/7 Flutterfälle, Browser; Disposition, signierter Bericht, Wartung, Lösung und Wiedereröffnung; `CRM_ERP_SERVICE_CLIENTS.md` |
| Auftragskette B/C | Zwei echte PostgreSQL-Journeys verbinden Auftrag, Teil-/Restlieferung, Offline-Bericht, Zahlung, Projektkosten, EÜR, Inventur, Gerät, Service und Dump/Restore; `CRM_ERP_KUNDENAUFTRAG.md` |
| Bankabgleich | 17 Fach-, 3 PostgreSQL-/MFA-/Parallelitäts-/Restore-Fälle, 11 Node-/11 Flutterfälle, echter Browser mit Teil-/Vollzuordnung, Nullaktivitätsauszug und unveränderten Exporten; `CRM_ERP_BANKABGLEICH_CLIENTS.md` |
| Betriebsmittel | 8 Fachfälle plus 19 Planung-/Serviceregressionen, 2 lokale HTTP-/2 PostgreSQL-Fälle, 24 kombinierte Node-/13 Flutterfälle, Browser mit Nutzungssperre und Originalen; `CRM_ERP_BETRIEBSMITTEL_CLIENTS.md` |
| Bestelländerungen/Retouren | 118 Fach-/Integrationsfälle, 96 überlappende unabhängige Regressionen mit sieben eigenen Gegenproben und drei PostgreSQL-/Restorefälle; beide Clients und historische Originale; `CRM_ERP_EINKAUF_RETOUREN.md` |
| Zusätzliche Firmeninstanz | 29 Domain-/Guardfälle, drei tatsächliche Zweifirmen-/MFA-/Restorefälle, separater Linux-UID-Test und vier bestehende Release-/Restorefälle; kein produktiver Host eingerichtet; `CRM_ERP_PROVISIONIERUNG.md` |
| Midijob-Vollmonate | 67 lokale Lohnfälle, drei neue und neun bestehende PostgreSQL-Fälle, 37 kombinierte Node-/41 Flutterfälle und echter Browser; explizite Prognose, getrennte Beiträge, Korrekturen und historische Originale; `CRM_ERP_LOHN_MIDIJOB_2026.md`, `CRM_ERP_LOHN_MIDIJOB_CLIENTS.md` |
| Bedienbarkeit | 18 tatsächlich gerenderte Browseransichten ohne automatische axe-Verletzung, Tastaturdialog und mobile Überlaufprüfung; menschliche/gerätebezogene Abnahme bleibt offen; `CRM_ERP_BEDIENBARKEIT.md` |
| Abhängigkeiten | Gefundene Python-Meldungen durch überprüfte Pins behoben; erneute Python/npm/Dart-Prüfung ohne bekannte Meldungen, reproduzierbares Inventar von 153 Quellkomponenten; `CRM_ERP_ABHAENGIGKEITEN_SICHERHEIT.md` |

## Laufende Fertigstellung

1. Gemeinsame Regression am stabilisierten Stand mit Lieferantenretouren, Bankabgleich, Betriebsmitteln und Midijob. Zwei unabhängig reproduzierte Retouren-Integritätsbefunde sind behoben; beide Clients bewahren historische Quittungen.
2. Nächste Lohnfälle: belegte Zeitachsen und Teilmonate. Midijob-Vollmonate sind abgeschlossen und oben nachgewiesen. Weitere Standardfälle stehen konkret im `CRM_ERP_LOHN_LUECKENPLAN_2026.md`; Reisekostenpauschalen werden parallel vorbereitet.
3. Zweite Unternehmensinstanz: technische lokale Provisionierungs-/Restoreprüfung abgeschlossen, einschließlich vier bestehender Betreiberregressionen. Tatsächliche Hostinstallation und Betriebsabnahme bleiben gesondert. Keine öffentliche Bereitstellung.
4. Abschließende gemeinsame Regression am stabilisierten Quellstand; bestehende Einzelabnahmen werden nicht als Ersatz dafür ausgegeben.

Weitere unabhängige Zielarbeit bleibt offen: alle vereinbarten steuerlichen
Einzelfälle, vollständige Betriebs-/Geräteabnahmen
und durchgängige Abnahmen A–G. Tatsächliche Anbieterexporte und Liveanbindungen
werden nicht durch ein neutrales Dateiformat vorgetäuscht. Fehlender Code wird
nicht als externe Blockade umetikettiert.

## Gemeinsame Integration

Erweiterungen verwenden additive Module. Alte Schema-Definitionen, Quittungen
und historische Beweise werden nicht neu interpretiert. EÜR erweitert den
Finanzvergleich nach Restore zunächst auf Horizont 8/Prüfberichtschema 9;
die Lohnzahlungsbrücke ergänzt Horizont 9/Prüfberichtschema 10 und der
Bankabgleich Horizont 10/Prüfberichtschema 11. Nach dieser Integration bestehen
49 bisherige Finanz-HTTP-Regressionen und neun Lohnzahlungs-Fachfälle.
Historische Berichte bleiben überprüfbar; neue Restores verlangen den aktuellen
vollständigen Finanzumfang.

Offene Fachbefehle behalten Daten und Anfrage-IDs. Vor Wiederholung werden
Rechte/Quellen frisch geprüft. Sitzungswechsel oder verspätete parallele
Antworten dürfen keinen neueren Auftrag überschreiben. Versandregeln greifen
auch an nativen Versandwegen direkt vor dem Transport. Wiederhergestellte
Assistentenaufträge werden angehalten; Versandunsicherheit bleibt erhalten.

Der letzte breite Zwischenlauf vor den jüngsten Ergänzungen bestand mit
734 Backendtests (733 bestanden, 1 Windows-Skip unter Linux) und 211 Node-Tests.
Dies ist ausdrücklich kein aktueller Gesamtlauf aller inzwischen ergänzten
Module. Nach dem Abhängigkeitsupdate bestanden 95 kaufmännische Tests und 67
Planimporttests. Der gemeinsame Node-Zwischenlauf bestand mit 284 Tests, die
Paketprüfung mit 16 Tests. Unternehmensübersicht und mobile Darstellung wurden
mit der neuen Python-Laufzeit erneut tatsächlich im Browser geprüft. Der erste
breite Backendlauf mit neuen Bibliotheken hatte 848 erfolgreiche Tests, einen
Windows-Skip und einen inzwischen gezielt korrigierten HTTP-Test; er wird nicht
als vollständig grüner Gesamtlauf ausgegeben. Gemeinsame Abschlussregression
folgt nach Stabilisierung der laufenden Erweiterungen. Rohprotokolle liegen unter `work/verification/`.

## Noch notwendige externe Nachweise

Kein realer Modell-/Sprachanbieter, keine produktive Bank-/Bestell-/Meldestrecke
und keine öffentliche Bereitstellung wurden durch Entwicklungstests
freigegeben. Reale Windows-/iPhone-Installation und Gerätefunktionen,
unabhängige Sicherheitsprüfung sowie zuständige fachliche/rechtliche Freigaben
bleiben gesonderte Nachweise. Amtliche Meldungen benötigen die jeweiligen
Zugänge, Prüfungen und Zulassungen. Das Gesamtziel ist noch nicht erreicht.


### Weitere Zwischenregression nach Integration

Der nächste breite Lauf führte 915 Tests aus: 913 bestanden, ein Windows-Fall
wurde unter Linux ausgelassen, ein Servicefall brach mit einer unvollständigen
internen Benutzeridentität ab. `Service.sources` lädt die vollständige Identität
inzwischen frisch; der identische gezielte Fall besteht, ebenso die aktuelle
Service-Domänen-/PostgreSQL-Abnahme. Der breite Lauf hatte den vorherigen Stand
bereits importiert und wird nicht nachträglich als grün bezeichnet. Die
13 gemeinsamen Flutter-Sitzungs-/Übersichts-/Shellfälle bestanden erneut.

Maschinenlesbare Zwischenläufe mit tatsächlichen Loghashes:
[evidence/integration-runs-2026-11-03.json](evidence/integration-runs-2026-11-03.json).
Die finale gemeinsame Regression folgt am stabilisierten gesamten Quellstand.


### Breiter Bank-/Betriebsmittelstand und gefundene Clientfehler

Der nächste vollständige Backendlauf besteht: 950 Fälle, 949 bestanden und
nur der Windows-Jobobjektfall unter Linux ausgelassen (268,575 s). Alle 323
Node-Vertragstests bestehen (3,562 s). Diese Läufe liegen vor den nachfolgenden
Retouren- und Midijob-Erweiterungen.

Die vollständige Flutterprüfung führte 835 Tests aus: 827 bestanden, acht
schlugen fehl, keiner wurde übersprungen. Ein neuer Bankdialog hatte eine
ungültige leere Datumsvorbelegung; sieben Rechtewidgettests verwendeten die
veraltete Portalbeschriftung. Die Ursachen wurden korrigiert; die tatsächlichen
Folgeläufe (elf Rechtefälle und elf abschließende Bankfälle) bestehen. Der erste
Gesamtlauf bleibt ausdrücklich als fehlgeschlagen dokumentiert. Details:
`CRM_ERP_FLUTTER_GESAMTPRUEFUNG_2026-11-03.md`.

Eine zusätzliche Transportkorrektur behandelt lokal zu große Antworten als
unbestätigt. Sie dürfen keine bereits angenommene Mutation samt Anfrage-ID
verwerfen. Nur definierte Bank-JSON-Endpunkte erhalten die größere begrenzte
Antwortgröße; allgemeine JSON-/Dateigrenzen bleiben bestehen. 31 Node- und
16 Flutter-/echte HTTP-Fälle prüfen dies einschließlich einer über 20 MiB großen
Bankantwort. Die Betriebsdaten bleiben bei unklarer Antwort unverändert
wiederholbar.


### Gemeinsame Clientregression am eingefrorenen Stand

Der anschließende Node-Gesamtlauf besteht mit 336 von 336 Tests, ohne Fehler
oder Auslassungen (2,466 s). Die vollständige Flutterregression besteht mit
848 von 848 Tests aus 98 Suiten, ohne Fehler oder Auslassungen (228,669 s).
Die vollständige Flutteranalyse meldet keine Befunde (6,2 s); der Quellsnapshot
wurde während dieses Laufs nicht geändert. Der vorherige fehlgeschlagene
835-Test-Lauf bleibt im [Gesamtprüfbericht](CRM_ERP_FLUTTER_GESAMTPRUEFUNG_2026-11-03.md)
erhalten. Diese Ergebnisse schließen die breite Backend- und tatsächliche
Browserregression nicht automatisch mit ein.


### Gesicherter Entwicklungs-Checkpoint `31c5184`

Der gesamte bisherige Entwicklungsstand ist lokal committed; kein Remote-Push
oder produktiver Rollout wurde ausgeführt. Die vollständige Backendregression
am eingefrorenen Stand besteht mit 989 Fällen: 988 bestanden, allein der
Windows-Jobobjektfall unter Linux ausgelassen (279,212 s). Die vollständige
Paketprüfung einschließlich finaler Retourenanleitung besteht mit 16/16 Fällen
(5,180 s). Das reproduzierte Quellinventar bleibt bytegleich bei 153 Komponenten.
Zusammen mit den bereits dokumentierten 336 Node- und 848 Flutterfällen bildet
dies einen konkreten Entwicklungsnachweis. Der lange gemeinsame Browserlauf
läuft noch; er wird erst nach vollständigem Runnerabschluss als bestanden
gezählt. Die nächste Entwicklung beginnt in eigenen neuen Moduldateien, während
die bereits laufende Browserprüfung ihre eingefrorenen Oberflächen behält.


Der abschließende gemeinsame Browserlauf des Checkpoints hat alle 17 Abläufe
bestanden: tatsächliche MFA-/HTTP-Anmeldung, Rechte-/Modulwechsel, Portal,
Buchführungsketten, Einkauf, Planung, Originaldateien, Signatur, Lagerrolle,
mobile Ansichten und Anfrageformular. Namespace-, PID-, Netzwerk- und
Seccomp-Sandbox wurden vor dem Anwendungszugriff tatsächlich geprüft. Die
Browserdateien blieben bis zum vollständigen Runnerabschluss unverändert;
der Testdienst hatte den Checkpoint bereits vor der folgenden Backendintegration
geladen. Keine Aussage über produktives TLS oder reale Windows-/iPhone-Geräte.


## Ergänzung: Lohnteilmonate und Reisekosten-Finanzintegration

P2-Lohnfakten und P3a-Teilmonate sind im beschriebenen Umfang abgeschlossen:
27 Fakten-/Transport-/Gegenprüfungen und drei echte PostgreSQL-Fälle;
120 Lohnregressionsfälle, drei neue PostgreSQL-Teilmonatsfälle sowie neun
historische PostgreSQL-Fälle nach gezielter Anpassung der aktuellen
Restoreumfang-Erwartungen. Die alten Regelmodule bleiben bytegleich.
Die Client-Abnahme umfasst 51 Node-, 52 Flutterprüfungen, Analyze und einen
echten MFA-/HTTP-Browserablauf einschließlich 390-Pixel-Darstellung.
Diese Zahlen überlappen und sind keine addierbare Gesamtzahl. Nachweise:
[Teilmonate](CRM_ERP_LOHN_TEILMONATE_2026.md),
[Fakten](CRM_ERP_LOHN_FAKTEN_2026.md),
[Clients](CRM_ERP_LOHN_ZEITACHSEN_CLIENTS.md).

Die neue tatsächliche Reisekostenzahlung ist mit EÜR und Bank verbunden:
sechs eigene Kettenfälle und bestehende Lohnzahlung-/Bankregression bestehen
gemeinsam mit **32/32** Prüfungen. Hinzu kommen **49/49** Finanz-HTTP-Prüfungen
und je **5/5** unabhängige öffentliche Quellenprüfungen in Node und Flutter.
Belegt sind Teilzahlungen ohne Vorsteuer, Finanzzugriff ohne Personalquellen,
Periodensperren, dokumentarische Aufhebung ohne erfundene Rückzahlung,
unveränderte alte Exporte und kompletter Restoreumfang11/Bericht12.
Der Gegenversuch fand eine doppelt verwendbare alte Zahlungsreferenz;
der neue Writer sperrt diese nun. Beide Clients wiesen zuvor unmögliche
Kalendertage nicht ab; dieser Fehler ist ebenfalls behoben.
[Testprotokolle und Quellhashes](evidence/travel-finance-integration-2026-11-03.json)
bewahren Umfang und frühere fehlgeschlagene Prüfungen nachvollziehbar.

Weitere Reise-/Auslagen-/Lohnfälle und ihre gesamte Browser-/PostgreSQL-Abnahme
sind weiterhin in Arbeit. Der reduzierte eigene Mitarbeiterbeleg für v1–v4
ist inzwischen geprüft; die Verbindung mit der neuen v5-Abrechnung folgt.
Dieser Zwischenstand ist keine Gesamtfertigstellung.

## Ergänzung: Anspruchsnachweise, eigene Belege und neue Gesamtfälle

Die eigene Mitarbeiteransicht für v1–v4 enthält eine begrenzte Abrechnung,
unveränderliches PDF und Historie. Ihre Abnahme umfasst acht Domänen-/HTTPfälle,
55 Node- und 56 Flutterprüfungen sowie einen tatsächlichen Browserablauf mit
zwei MFA-Sitzungen, Rechteentzug und 390-Pixel-Ansicht.
[Nachweis und Grenzen](CRM_ERP_LOHN_MITARBEITERBELEG.md).

Die Reisekostenclients bestehen ihren abschließenden v2-Browserablauf
einschließlich belegter Auslagen, alter Erstattungen, Berichtigung, Aufhebung
und EÜR. Zusätzlich sind 44 Node- und 44 gezielte Flutterfälle, zwölf private
Flutterfälle sowie Analyze dokumentiert. Ein früherer Katalogfehler nach dem
Umgebungsneustart war nicht reproduzierbar; der fehlgeschlagene Lauf bleibt
erhalten, eine nachgewiesene Ursache wird nicht erfunden.
[Clientprotokolle](evidence/travel-clients-2026-11-03.json).

Die unabhängige Prüfung der Anspruchsquellen fand eine Möglichkeit, eine
spätere Personalrevision einem früher angenommenen Auftrag zuzuordnen.
Der private Originalauftrag wird jetzt zusätzlich an seine tatsächliche
Quittung gebunden; alle acht Gegenprüfungen bestehen. Die neue Krankheitsregel
v2 zählt bei Stundenlohn und AU-Beginn am freien Tag ab dem Folgetag, während
historische v1-Nachweise unverändert bleiben. Fünf zusätzliche unabhängige
Rechenfälle prüfen Kalendergrenzen, Wiedererkrankung und Wartezeit.
[Anspruchsprüfung](CRM_ERP_LOHN_ANSPRUECHE_GEGENPRUEFUNG_2026.md).

Die neue v5 verbindet kanonische Beschäftigungssegmente, bestätigte Ansprüche
und Reise-Lohnwerte. Sechs unabhängige private Gegenprüfungen bestehen:
Ansprüche können nicht durch Weglassen umgangen werden; Originalquittungen
bleiben nach späteren Quellenänderungen wiederholbar; entzogenes Freigaberecht
verhindert auch Wiederholungen. Eine aktuelle PostgreSQL-Prüfung fand einen
untypisierten NULL-Parameter in der globalen Steuerentscheidungsabfrage.
Die Abfrage wurde in getrennte statische Prädikate aufgeteilt; die abschließende
Transport-/Restoreprüfung läuft. Die neue Registrierung und Paketzuordnung
sind vorhanden; die vollständige Clientabnahme steht noch aus.
[Private Gegenprüfung](evidence/payroll-calculation-cases-private-review-2026-11-03.json).

Der eigenständige 25-%-Reisepauschalsteuerhelfer besteht 21 eigene und
unabhängige Fälle, einschließlich Nebensteuern, belegter unbekannter
Kirchenzugehörigkeit, Fristen und genehmigtem Arbeitnehmerabzug.
Die tatsächliche Steuererfassung wird erst beim Lohnabschluss gespeichert;
eine Vorschau behauptet keine erfolgte Zahlung oder Übermittlung.
[Steuerprüfung](CRM_ERP_REISE_PAUSCHALSTEUER_GEGENPRUEFUNG_2026.md).
Der neue PAP-Helfer für Einmalbezüge besteht zusätzlich vier unabhängig von
seiner Implementierung hergeleitete Rechenfälle; ein fertiger Einmalbezugsablauf
ist damit noch nicht nachgewiesen.

## Geprüfter Quellstand 2fdfa9f – 03.11.2026

Der lokale Commit `2fdfa9f37bbbaf9e8b6fe4070be6809fe15b69c3` sichert die isoliert geprüfte Zusammenführung der Lohnquellen, Gesamtfälle und Reise-/Finanzabläufe. Auf genau diesem eingefrorenen Quellstand bestanden 1.484 von 1.485 Backendtests (ein Windows-spezifischer Test unter Linux ausgelassen), 398 Node-Tests und 932 Flutter-Tests; die vollständige Flutter-Analyse meldete keine Probleme. Quelldateien und Protokolle sind mit SHA-256 im Nachweis `docs/evidence/payroll-travel-core-regression-2026-11-03.json` und dem zugehörigen Dateimanifest gebunden.

Der erste Flutter-Start scheiterte an einem fehlenden Testinterpreter-Pfad und wurde abgebrochen; der anschließende vollständige Lauf mit dem vorhandenen verifizierten Interpreter bestand. Spätere globale Jahres-/U-Registrierungen, die neueren P4-Oberflächen sowie Einmalbezug-v6 liegen außerhalb dieses eingefrorenen Nachweises. Sie werden weiter implementiert und gesondert geprüft. Der Commit ist ein lokaler Entwicklungszwischenstand, keine Behauptung eines abgeschlossenen Gesamtziels oder einer Produktivfreigabe.

## Weiterentwicklung am 04.11.2026: Jahresquellen, Nullnetto und Einmalbezüge

Die fünf privaten Jahresquellenarten besitzen Browser- und App-Formulare. Die unabhängige App-Gegenprüfung fand und behob verbliebene Dialoge nach Mitarbeiter-/Sessionwechsel und entzogenem Freigaberecht; zehn gezielte Gegenfälle sind nach dem Fix grün. Die Wiederholungsprüfung der geschützten Browser-Lohnpfade besteht61Tests. P4 und Gesamtfälle wurden zusätzlich gegen spät eintreffende private Fehlertexte abgesichert.

Ein tatsächlicher Nullnettomonat kann jetzt mit Originalbeleg und leerer Zahlungsteilliste dokumentiert werden, ohne einen Geldfluss zu erzeugen. Positive Abführungen bleiben separat zu belegen. Domain-, PostgreSQL- und Clientnachweise liegen unter `CRM_ERP_LOHN_NULLMONAT_PRUEFUNG_2026-11-03.json`; die Browser-Gesamtregression wird getrennt fortgeschrieben.

Die neue Source4-Kette für reguläre Einmalbezüge ist in Entwicklung: kanonische Jahresquellen, geschützte Fallannahme, ein dauerhaft an seinen Lohnlauf gebundener Anspruch, tatsächlicher Zahlungsnachweis, Cash und EÜR. Vier unabhängige private Quellen-/Rechtegegenfälle bestehen. Die globale Registrierung aller drei Tabellen, der Unternehmensübergabe und der Quellpakete besteht48Tests (11,138s). Nachweise: `evidence/payroll-oneoff-private-independent-2026-11-03.json` und `evidence/source4-three-table-registration-2026-11-04.json`. Die vollständige PostgreSQL-/Browser-/App-Abnahme dieser neuen Kette ist damit noch nicht erklärt.

Weiter offen bleiben unter anderem weitere Jahreszuordnungen nach bereits abgerechneten Einmalbezügen, mehrere Boni und unterschiedliche tatsächliche Zuflusstage sowie die im Lohn-Lückenplan ausdrücklich benannten Versicherungs- und Meldefälle. Das Gesamtziel bleibt die vollständige Software; ein geprüfter Teilumfang wird nicht als Gesamtabschluss ausgewiesen.

## Source4-Jahresfortschreibung und weitere Gesamtzielarbeit – 04.11.2026

Die bezahlte Source4-Zusammenrechnung fließt jetzt in spätere Jahresbasen und
Steuerprognosen ein. Laufendes Entgelt und frühere Boni bleiben getrennt; ein
Märzklauselbonus verbraucht die tatsächliche Vorjahres-SV-Basis, ohne dadurch
falsche Beschäftigungstage im Vorjahr zu erzeugen. Bei Korrektur desselben
Anspruchs wird dessen bisheriger Verbrauch ersetzt. Acht gezielte Jahresfälle
bestehen in einer gemeinsamen 55-Fälle-Prüfung (90,742 Sekunden). Drei echte
Monatsläufe bleiben zwischen 206.183 und 228.168 Bytes; der vollständige
Drei-Monats-Quellenkatalog umfasst 2.340.035 Bytes. Nachweis:
`evidence/payroll-oneoff-annual-followup-2026-11-04.json`.

Die finale zusätzliche PostgreSQL-Prüfung besteht vier Fälle (46,480 Sekunden),
einschließlich tatsächlichem Backup/Restore der bezahlten Jahresfortschreibung:
`evidence/payroll-oneoff-pg-annual-final-2026-11-04.json`. Der aktuelle Source4-
Vertrag ist in `CRM_ERP_LOHN_EINMALBEZUG_V6_VERTRAG_2026.md` beschrieben.
Mehrere Boni im selben Monat, verschiedene Zuflusstage und abhängige
Folgekorrekturen bleiben benannte Entwicklungsarbeit.

Außerhalb Lohn/Reisen wurde das Gesamtziel erneut mit der Runtime verglichen.
`CRM_ERP_GESAMTZIEL_GEGENPRUEFUNG_2026-11-04.md` beschreibt konkrete weitere
Pakete zu Finanzübernahme, Katalogpreisen und Ereignisregeln. Die Übernahme
belegter Konto-Anfangssalden entsteht in einem isolierten Arbeitsbaum und
ist noch kein Bestandteil eines freigegebenen Hauptrepository-Stands.

## Geprüfter gemeinsamer Commit 5d9e7fd – 04.11.2026

`5d9e7fd2cc0f04ef46d25d112549408454c6519a` sichert den gemeinsam geprüften
Source4-Stand. Ergebnis: 1.508 bestandene Backendtests und eine
plattformspezifische Auslassung, 473 JavaScript- und 1.103 Fluttertests,
16 Paketprüfungen und vollständige Flutteranalyse ohne Befund.
Nachweis und Grenzen: [Source4-Gesamtprüfung](CRM_ERP_SOURCE4_GESAMTPRUEFUNG_2026-11-04.md).

Vier Fehler des ersten Backendlaufs waren auf unterschiedliche Testuhren
zurückzuführen; zwei Testdateien wurden berichtigt und ein echter
Tageswechsel-Gegenfall ergänzt. Der Produktcode blieb dabei unverändert.
Der erste Paketlauf benötigte den fehlenden lokalen Testinterpreter-Pfad.
Alle Erst-/Folgelogs und beide Quellmanifestfassungen bleiben erhalten.
Beim Fortschreiben des Hauptbranchs wurden die Inhalte sämtlicher 1.531
vorhandenen Arbeitsdateien per SHA-256 unverändert nachgewiesen; laufende
V7-Arbeit blieb erhalten. Kein Remote-Push oder Produktivrollout erfolgte.

Die Entwicklung geht mit Anfangssalden, Katalogimport und weiteren
Lohn-/Zahlungsfällen weiter. Die hierfür entstehenden separaten Arbeitsstände
sind noch kein Teil dieses überprüften Commits und kein Gesamtabschluss.

## Gemeinsamer Checkpoint am 04.11.2026: Anfangssalden und Katalogoriginale

Die Zusammenführung auf Basis `5d9e7fd` besteht 1.565 von 1.566 Backendtests
(ein Windows-spezifischer Skip), 522 Node- und 1.118 Fluttertests. Analyse ohne
Befund, 16 Paketprüfungen und beide tatsächlichen Browserabläufe sind grün.
Zehn gemeinsame PostgreSQL-Fälle und ein zusätzlicher befüllter Katalog-/Opening-
Restore bestehen. Alle 1.626 eingefrorenen Dateihashes waren nach den Prüfungen
unverändert; Original-Gesamtziel und bestehende Source4-Verträge bleiben erhalten.
[Ergebnisse und Grenzen](CRM_ERP_ANFANGSSALDEN_KATALOG_GESAMTPRUEFUNG_2026-11-04.md).

Behoben wurden ein verbliebener privater Kontoname im Dialogtitel nach
Rechteentzug, späte private Quellen nach Kontextwechsel und die erneute Anwendung
der Einzeleingabegrenze auf bereits berechnete große Kontensummen. Browser und
Flutter prüfen dieselben tatsächlich angenommenen positiven/negativen Grenzfälle.
Der Katalogbaustein erhält unveränderte Originale, serverseitige Vorschau,
Annahmehistorie, begrenzte große Antworten und vollständige Paketregistrierung.

Source5-Backend und dessen sichere Mitarbeiterbelege/Clients, historische lineare
Anlagen, datierte Katalogpreise v2 und die native Kataloghistorie laufen separat
weiter. Ihre Teilnachweise gehören nicht zum neuen eingefrorenen Gesamtstand.
Unternehmensweite Ereignisregeln und verbleibende Lohn-/Steuerfälle sind weiterhin
Implementierungsarbeit. Es wurde keine Produktivmigration oder Gesamtabnahme
behauptet.

## Native Kataloghistorie nach c7dbab0 – 04.11.2026

Der bisherige native Dateiimport besitzt jetzt dieselben unveränderten Originale,
Annahmehistorien und serverseitigen Vorschauen wie der Browser. Der gemeinsame
Sessioncode bewahrt Opening- und Source4-Aufträge und erhält einen eng begrenzten
Katalog-Replaypfad. Reale HTTP-Prüfungen belegen 2 MiB mit 2.000 Artikeln in Unicode sowie
die genaue Grenze von 32 MiB für Katalogantworten und deren Überschreitung um ein Byte.
Die vollständige integrierte Flutterregression besteht 1.163/1.163; Analyse ohne
Befund. Backend und Browser bleiben exakt auf dem geprüften c7dbab0-Stand.
[Prüfumfang und Nachweise](CRM_ERP_KATALOG_NATIVE_2026-11-04.md).
Source5, historische Anlagen und datierte Preisquellen sind weiter getrennte
Entwicklungsarbeit und in diesem Clientcheckpoint nicht enthalten.
