# Jahresprüfstand mit Originalen und Journalentscheidungen

Arbeitsstand 04.11.2026. Eigenes Smartplan-Format, kein DATEV-Importformat,
keine Steuererklärung und keine Herstellerfreigabe. Anforderungen: Gesamtziel
Abschnitte 8 und 13, R08.07 sowie die belegte R08-Restprüfung nach Anlagen und
Altposten. Der bestehende Export `smartplan_euer_review_v1` bleibt unverändert.

## Feste Grundlage und Versionierung

Ein Paket ergänzt genau einen bereits ausdrücklich bestätigten EÜR-Exporteintrag.
Seine ID, sein Originalhash, sein Jahr, sein Journalpräfix, sein ursprüngliches
Profil sowie Report- und CSVbytes bilden die unveränderliche Grundlage. Es wird
kein heutiger Report unter einer alten Exportkennung neu berechnet. Spätere
Buchungen, Quellkorrekturen und Profilwechsel ändern dieses Paket nicht.

Version 1 wird rein lesend und deterministisch abgeleitet. Sie benötigt keine
neuen Finanztabellen, keinen weiteren Migrations-/Restorehorizont und keine neue
wirtschaftliche Buchung. ZIP-Einträge erhalten feste Zeitstempel, feste Sortierung
und unkomprimierte Bytes; der Ausgabeinhalt hängt nicht von Uhr, Benutzer,
Zufallskennung oder Kompressionsbibliothek ab. Dieses Format und sein
mitgelieferter Prüfer müssen nach Freigabe als v1 erhalten bleiben. Zukünftige
Formatänderungen erhalten eine andere Version, statt alte Paketbytes zu verändern.

Die Unternehmensidentität muss über die vorhandene Operatorbindung feststehen.
Anlage und Download prüfen dieselbe aktuelle fachliche Berechtigung. Es gibt
keine öffentliche Freigabe, keinen Versand und keinen Zugriff auf Provider.

## Auswahl und gebundene Nachweise

Die unabhängige Gegenprüfung hat die Grenze alter Journale belegt: Ein
nachträglich erzeugtes Auswahlverzeichnis ist nicht bereits durch den alten
Exporteintrag kryptografisch gebunden. Mengenidentische frühere Zahlungen sind
ebenfalls kein Beweis ihrer ursprünglichen Identität. Das Paket enthält die
aufgelösten Originale, behauptet aber keine intrinsische Vollständigkeit sämtlicher
Abhängigkeiten. Ein vollständiges fremdes Journal wird zur Umgehung dieser Grenze
nicht beigefügt; alte Exportoriginale werden nicht nachträglich verändert.

Jede Verifikation benötigt deshalb den separat in der authentisierten Sitzung
bestätigten Archivhash. Ohne oder mit falschem Hash verweigert der Prüfer die
Verifikation. Manifest und Ergebnis nennen `intrinsic_dependency_closure=false`.
Die vorhandenen inneren Bindungsprüfungen bleiben zusätzliche Kontrollen; ihr
Erfolg begründet keinen eigenständigen Vollständigkeitsbeweis. Ein selbst
mitgelieferter Hash kann die externe Vertrauensbindung nicht ersetzen.

Enthalten sind die exakten bisherigen Report-/CSVdaten, der Exporteintrag mit
seinem originalen Annahmebefehl sowie alle zugehörigen EÜR-Entscheidungen. Die
Auswahl umfasst Jahrespostings, ausdrücklich im alten Report enthaltene Quellen
und Anlagen, zugehörige Gegenbuchungen/Korrekturen und notwendige frühere
Entscheidungen derselben Quellen. Andere Jahre werden nur als benötigter
Herkunfts- oder Korrekturbeleg aufgenommen. Andere Quellen werden nicht allein
wegen ihrer zeitlichen Nähe kopiert. Die übrigen Journalpositionen erscheinen
höchstens als Sequenz-/Hashbindung ohne fachlichen Inhalt.

Jede eingeschlossene Quelle erhält einen versionierten Nachweis mit den tatsächlich
gebundenen Originalen. Eingangsbelege verwenden die damalige geprüfte Revision,
Ausgangsrechnungen ihre finalen PDF-/XML-/Payloadfassungen, historische Anlagen
ihren Originalvortrag und Altpostenzahlungen Rechnung, Übergabenachweis,
ursprüngliche Zahlungs-/Vorsteuerbelege und die spätere tatsächliche Zahlung.
Notwendige dokumentarische Zahlungsaufteilungen bleiben nachvollziehbar.

Die zugelassenen öffentlichen Lohn- und Reisegeldprojektionen bleiben öffentliche
Finanzquellen. Private Personalakten, Einzelabrechnungen, Mitarbeiteroriginale
und private Reiseunterlagen werden nicht automatisch beigegeben. Der Prüfer
weist diese ausdrückliche Grenze aus und behauptet keine private Quellenprüfung.
Ein unbekannter Quellentyp wird nicht still ignoriert oder als belegt ausgegeben.

Nicht gebuchte Quellen und offene Fragen des damaligen Reports werden als offene
Fragen erhalten. Ein später vorhandener Beleg darf nicht rückwirkend als damals
geprüft eingefügt werden. Die Kontrolle der ausgegebenen Dateien ist von der
ursprünglichen fachlichen Jahresvollständigkeit und der oben begrenzten
intrinsischen Quellenvollständigkeit getrennt. Erkannte fehlende, gekreuzte oder
beschädigte notwendige Originalbindungen sperren die Ausgabe; sie werden nicht
durch Nullwerte oder einen bloßen Link ersetzt.

## Rechte und Offlineprüfung

Aktive Finanzleserechte und jede tatsächlich eingeschlossene Projekt-/Quellfreigabe
werden vor Ausgabe erneut geprüft. Eine Quellberechtigung rechtfertigt weder
andere Projekte noch Personaldaten. Der Abruf eines alten Pakets umgeht keinen
Rechteentzug. Der vorhandene Datenbank-Snapshotmechanismus verhindert einen
gemischten Stand während des Abrufs. Restorefreigaben für neue Finanzmutationen
werden durch den rein lesenden Zugriff nicht verändert.

Das ZIP enthält ein geschlossenes Dateiverzeichnis mit Größen und SHA-256 sowie
einen eigenständig mit der Python-Standardbibliothek ausführbaren Prüfer. Dieser
prüft Dateiliste, Originalhashes, Journalhashes, Originalannahmen, Korrekturverweise,
Jahrespostings, CSVdarstellung und Summen. Er extrahiert oder startet keine
Archivdateien und kontaktiert keine Anwendung. Der separat angezeigte ZIPhash
bindet den Download; interne Hashkonsistenz allein ist keine Signatur. Ein fremdes
Archivskript wird nicht ohne Herkunftsprüfung gestartet.

## Reale Abnahmen

1. Bezahlter Einkauf, Teilzahlung auf Ausgangsrechnung und spätere Kontokorrektur:
   alte Bytes bleiben nach weiteren Buchungen identisch, alle benötigten Originale
   und ursprünglichen Entscheidungen sind enthalten.
2. Historische Anlage und Altposten mit schon früher ausgeübter Vorsteuer:
   benötigte alte Nachweise sind vorhanden; es entsteht kein neuer Geldfluss und
   kein weiterer Vorsteuerabzug.
3. Aggregierte Lohn-/Reisequelle: öffentliche Finanzwirkung ist prüfbar, private
   Namen/Unterlagen und ein unbeteiligtes Projekt fehlen tatsächlich.
4. Lokaler Prüfer nach Schließen der Officeinstanz: manipulierte CSV, fehlende
   Originalbytes, gekreuzte Quellhashes und abgeschnittene Korrekturgeschichte
   werden abgewiesen. ZIP-Duplikate und unzulässige Dateipfade werden abgewiesen.
5. Tatsächliche HTTP-/Clientdateiablage, frischer Rechteentzug und befüllter
   PostgreSQL-Restore erhalten die feste Exportrückbindung.

## Manifestierte Basis und parallele Arbeit

Basis ist `b0b96024f0a7cf2c7097fb3b77c64032265850a5` mit ausschließlich dem
eingefrorenen Altpostenbackend-Handoff
`4fc7db209ebf5ce98799400d330182692f88ffdb5c9b9e1e924649385c6f3a88`.
Dessen 56 Dateien wurden aus dem archivierten Patch rekonstruiert und gegen
`80e051a28ad6ffe2b25818ed26d198f49ebb0c09` zusammengeführt; Source5, Anlagen,
Katalog-V2 und Kostenfix bleiben erhalten. Keine unfertigen Altpostenclients
wurden kopiert. Ausgangshashes und 50 bestandene Domain-/EÜR-Fälle stehen unter
`work/verification/year-review-export-baseline.json`.

Der parallele Jahresvortrag hat den vorgesehenen Finanzhorizont 15 / Restorebericht
16. Dieses Paket belegt keine dieser Nummern. Sobald dessen tatsächlicher
Quellenvertrag stabil ist, wird er ausdrücklich in die Auswahl aufgenommen;
unbekannte zukünftige Quellen dürfen bis dahin keine Vollständigkeit vortäuschen.
