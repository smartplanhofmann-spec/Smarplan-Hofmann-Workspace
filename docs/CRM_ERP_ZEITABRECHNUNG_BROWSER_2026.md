# Freigegebene Projektzeiten im Browser-Belegentwurf

Stand: 09.11.2026. Bezug: Originalziel §5, §6 und §11; R05.03/R06.04.

Die lesende Bestandsprüfung auf d4df2f5 fand einen konkreten fehlenden
Bedienweg: Eine tatsächlich erfasste und freigegebene Stunde war über die
bestehende API verfügbar, im Browser-Belegdialog jedoch nicht auswählbar.
Die manuelle Ersatzposition hatte keine Zeitquellenbindung. Backend und
native App besaßen die Funktion bereits. Der ursprüngliche echte
Chromium-/MFA-Nachweis bleibt unter
[evidence/browser-time-billing-2026-11-09](evidence/browser-time-billing-2026-11-09/)
erhalten; die anfängliche anderslautende Auditnotiz ist ausdrücklich korrigiert.

## Bedienweg und unveränderter Fachvertrag

Im Belegentwurf wird zunächst das Projekt ausgewählt. Unter
„Freigegebene Arbeitszeiten übernehmen“ sind einzelne vollständige
Zeiteinträge mit Datum und Sekunden auswählbar. Stundensatz netto und
Umsatzsteuer werden ausdrücklich eingegeben. Es werden höchstens 100
Einträge übernommen; Zeitquellen mit Nullsekunden sind nicht auswählbar.
Bereits im Entwurf gebundene Quellen werden getrennt von neuen Kandidaten
behandelt. Ein tatsächlich leerer anfänglicher Positionsplatzhalter entfällt
bei der ersten Zeitwahl; ausgefüllte freie und katalogbasierte Positionen bleiben.

Die bestehende API `/business/documents/time-sources` und ihre
`time_entry_ids`, `hourly_rate_net`, `time_tax_rate` bleiben unverändert.
Das Backend erzeugt Sekundenpositionen mit Preisbasis 3600 sowie bestehender
Eintragskennung, Revision und Quellhash. Der Browser übernimmt keine neue
Abrechnungsformel. Gespeicherte Zeitpositionen bleiben beim Bearbeiten im
Original erhalten und können ausdrücklich entfernt werden; sie werden nicht
in freie Positionen umgewandelt.

Vor Quellenanzeige und Übernahme werden aktuelle Projekt-, Beleg- und
Finanzrechte geprüft. Projekt-/Dialogwechsel und späte Antworten dürfen
keine fremden Auswahldaten oder erneut geöffneten Dialoge erzeugen. Eine
offene Antwort sperrt neue Eingaben und bietet ausschließlich den identischen
gespeicherten Auftrag an. Die Wiederholung prüft frische Rechte, verlangt
aber keine erneute Quellenverfügbarkeit: Eine schon angenommene Zeit kann
inzwischen ordnungsgemäß abgerechnet sein. Die offene Browseranfrage bleibt
wie zuvor im Arbeitsspeicher der aktuellen Sitzung.

Der bestehende Server importiert bei Annahme den dann aktuellen Zeitstand.
Der Browser prüft die Auswahl vor dem POST erneut. Ändert sie sich erst
zwischen diesem Abruf und der Annahme, wird der tatsächlich gespeicherte
Entwurf mit ausdrücklichem Prüfhinweis angezeigt. Diese enge Konkurrenzgrenze
wird nicht als atomar gesperrter Import ausgegeben. Eine Auswahl stellt nie
automatisch eine Rechnung fest. Die vorhandene serverseitige Prüfung bei
der Festschreibung schützt weiterhin gegen veraltete und doppelt
abgerechnete Zeitquellen.

## Zusätzlich reproduzierter PostgreSQL-Fehler

Der echte PostgreSQL-Browsernachlauf traf im unveränderten Zeitbackend auf
HTTP500 bei der Quellenliste: PostgreSQL liefert `SUM(BIGINT)` als exakten
NUMERIC-/Decimal-Wert; dieser gelangte in den kanonischen JSON-Quellhash.
Der Fehler wurde mit derselben gespeicherten Datenbank und tatsächlicher
`smartplan-online`-Rolle direkt reproduziert.

Nur die drei Summen über BIGINT-Sekundenspalten in Tageskorrekturen,
Kontokorrekturen und freigegebenen Eintragsanteilen erhalten jetzt ausdrücklich
ein BIGINT-Ergebnis. Geldfelder und allgemeine Decimal-Verarbeitung bleiben
unverändert. Es gibt keine Rundung fachlicher Bruchteile. Der neue dauerhafte
Test liegt in `backend/online/test_business_planning_time_pg.py` und wird von
der vorhandenen PostgreSQL-Testauswahl erfasst. Der eigenständige Backendfix
ist ad0071223eb4d1e74971cb8bf0f8da5efafcb9aa.

## Tatsächlich geprüfter Stand

- 952 Browsermodultests bestanden, darunter 14 neue Fälle zu Quellen,
  Rechten, Originalquittungen, Wiederholung und asynchronen Wechseln.
- 18 bestehende SQLite-Zeit-/Zeitabrechnungsfälle bestanden.
- Neuer tatsächlicher PostgreSQL-Regressionsfall bestanden: Nullsummen,
  negative/positive Zeitkorrekturen, numerische Zusammenfassung, kanonische
  Quellen und Kontokorrekturen.
- Drei Vergleiche der SQLite-Quellen einschließlich Hash und Zusammenfassung
  vor/nach der Änderung bestanden auf jeweils identischen Daten.
- Bestehender echter Browserablauf Kunde → Projekt → Angebot → Auftrag →
  Rechnungsentwurf bestanden; der bestehende Rechnungskettenablauf ebenfalls.
- Der kombinierte echte PostgreSQL-/MFA-/Chromiumablauf besteht: manuelle
  und katalogbasierte Positionen plus 7 Sekunden ergeben die belegte
  Zeitposition von 19,44 EUR; spätere Ergänzung erhält alle ursprünglichen
  Quellen. Eine echte Rechnung mit vier Positionen wird festgeschrieben,
  zwei Zeitbindungen und ihr PDF-Archiv werden unabhängig nachgelesen.
  Der konkurrierende Entwurf darf dieselben Zeiten nicht nochmals abrechnen.
  Der Test prüft Quellenänderung vor dem letzten Abruf, Änderung unmittelbar
  bei der Annahme mit sichtbarem Hinweis, Rechteentzug während Lost-ACK,
  unveränderte Wiederholung, 390px sowie verspätete Projekt-/Dialogantworten.
- Die separate Schlussprüfung bestätigt die tatsächliche Runtime-Rolle,
  deren Sicherheit, beide Integritätsprüfer und den Archiv-PDF-Hash.

Die ursprünglichen Fehlerprotokolle bleiben erhalten: falsche erste
Fixtureannahmen zur Owner-Sperre/Logout und zum HTTP-Erfolgscode, die korrekte
SQLite-Ausstellungssperre, die zu kurze erste PG-Startwartebedingung,
die korrekte Operator-only-Speicherbindung, der echte Decimal-Fehler,
falsche anfängliche Testimportpfade, ein zu früh gelesener Beleg während
noch laufender Festschreibung und der unprivilegierte Node-Unterprozess.
Sie werden nicht nachträglich als erfolgreiche Tests gezählt.

Keine Veröffentlichung, Kundenserverinstallation oder echte Geräteabnahme
ist mit diesem lokalen Nachweis verbunden. Die vollständige CRM-/ERP-Abnahme
bleibt eine getrennte Gesamtaufgabe.


Die neue gezielte Browserauswahl heißt `document-time-billing` in
`web/office/tests/e2e.cjs`. Sie verlangt eine eigene leere, durch
`SMARTPLAN_TEST_DSN` bezeichnete PostgreSQL-Datenbank `smartplan_check` auf
Loopback; die Fixture verweigert vorhandene Benutzertabellen und führt keine
automatische Datenlöschung aus. `serve_document_time_fixture.py` migriert die
leere Datenbank, trennt die Runtime-Rolle und bindet deren Speicher mit dem
Operator. Sie verwendet die unveränderte produktive Rechnungsausstellung,
keinen SQLite-Ausstellungsersatz. Der kurzlebige lokale Testcontainer wurde
nach gesicherten Ergebnissen entfernt.

Alle Rohlogs, die erfolgreiche Browserantwort und die unabhängigen
Datenbanknachweise sind im [Manifest](evidence/browser-time-billing-2026-11-09/manifest.json)
mit Dateihashes und, bei Gzip-Dateien, zusätzlichem Hash der ursprünglichen
Logbytes verzeichnet.
