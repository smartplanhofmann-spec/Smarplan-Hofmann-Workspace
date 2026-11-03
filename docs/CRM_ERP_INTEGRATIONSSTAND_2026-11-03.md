# Integrationsstand vom 03.11.2026

Entwicklungsstand, keine Produktivfreigabe. Projekt:
`/workspace/Smarplan-Hofmann-Workspace`, Branch `work`.
Das vollständige Gesamtziel und die Abnahmen A–G bleiben bestehen.

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
