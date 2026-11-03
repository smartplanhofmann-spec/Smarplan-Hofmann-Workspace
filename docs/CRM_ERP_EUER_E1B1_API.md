# E1b-1: zusätzliche Zahlungszuordnung – Implementierungsvertrag

Stand 02.11.2026, Basis `acb46b4`. Dieser Abschnitt konkretisiert einen
abgeschlossenen Teil des [E1b-Entwurfs](CRM_ERP_EUER_E1B_ENTWURF.md).
Er ist implementiert und mit den im [Fortschritt](CRM_ERP_FORTSCHRITT.md)
und [Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_E1B1.json) genannten Prüfungen getestet.

## Umfang und unveränderliche Grenzen

Additives Modul `business_accounting_allocations`, Feature
`accounting_payment_allocation`, bestehendes Unternehmensmodul `finance`.
Ein ausdrücklich bestätigter Befehl ordnet einen bisher freien Teil einer
bereits in E1a übernommenen Kundenzahlung genau einer normalen finalen
positiven EUR-Rechnung zu. Weitere Teilzuordnungen sind eigene Befehle.
Neue Geldflüsse, Steuerkomponenten, Refund-Ursprungsbeziehungen, Korrekturen,
Perioden und Exportprofile sind nicht Teil dieses Abschnitts.

Alte Payment-/Allocation-Zeilen, E1a-Quellenhashes, CashEvents und gespeicherte
Antworten bleiben unverändert. Neue eigene Tabellen speichern anhängende
Zuordnungseinträge und Anfragequittungen. Jede Zuordnung bindet Zahlung,
E1a-Ereignis, konkrete Rechnung/Archivhashes, den zuvor bestätigten Stand,
Betrag, Kundenbindung, Begründung, Akteur und Zeitpunkt. Historische
Modul-DDL, Guards und Checksummen werden nicht verändert.

Die Zahlung muss `receipt` sein, der CashEvent entsprechend `in`. Alle
ursprünglichen und zusätzlich verknüpften Rechnungen benötigen eine gemeinsame
nicht leere unveränderliche `customer_id`. Bei ursprünglich freier Zahlung
bestätigt der Benutzer den Kunden der gewählten Zielrechnung ausdrücklich;
die erste Zuordnung bindet diese Kundennummer. Referenztexte begründen keine
Kundenzugehörigkeit. Mehrkundenquellen und Quellen mit nicht unterstützten
Rechnungsarten bleiben lesbar, neue Zuordnungen sind gesperrt.

Neue Zielrechnung: `kind:'invoice'`, final, positive EUR-Gesamtsumme, kein
Abschlags-/Schlussrechnungsbezug und keine `deducts`-/`cancels`-Beziehung.
Spätere legitime Erstattungen oder Stornobeziehungen ändern keine historischen
Zuordnungsantworten. Neue Aktionen prüfen den jeweils aktuellen Zielzustand.

## Rechte und gemeinsame Projektion

Alle neuen Routen verlangen global `accounting.read` und `finance.read` sowie
aktuelle vollständige Quellleserechte. Vorschau/Bestätigung und Kandidatensuche
verlangen zusätzlich global `accounting.prepare`, global `finance.write`
und `finance.write` für sämtliche ursprünglichen, zusätzlichen und neu
betroffenen Zielprojekte. Neue Zielrechnungen benötigen ebenfalls ausdrücklich
`finance.read`; ein Schreibrecht ersetzt kein explizit entzogenes Leserecht.
Keine neuen Standardrechte.

Eine Zahlung wird nur als Ganzes offengelegt: alle ursprünglichen **und**
zusätzlichen Projektzuordnungen prüfen, bevor eine Quelle validiert oder
angezeigt wird. Ursprünglich unzugeordnete Zahlungen behalten immer ihre
Owner-/Erstellergrenze. Die Zuordnung zu einem Projekt erweitert diese Grenze
nicht. Rechte gelten auch bei historischen Replays und bereits gespeicherten
Exporten mit Zahlungssnapshots. E1a ergänzt nur diese frische Rechteprüfung;
sein ursprünglicher Beweis und sein Antwortformat bleiben unverändert.

Reine SQL-Lesehelpers des neuen Moduls ohne Rückaufrufe auf Finance/Accounting:
`effective_allocations(office,payment_id)` liefert aggregierte
`[{document_id,amount}]`, nach Dokument-ID sortiert;
`effective_paid(office,document_id)` liefert Decimal aus alten receipts,
neuen positiven Zuordnungen und alten negativen refunds;
`require_effective_payment_access(office,actor,payment_id,permission='finance.read')`
prüft den gesamten Umfang und die ursprüngliche private Grenze. Keine DDL.
Fehlt das Zusatzmodul vollständig, gilt der alte Stand; teilweise vorhandene
Tabellen/Migrationsdaten dürfen nicht als leerer Bestand behandelt werden.

Finance-Zahlungslisten, OP, Mahnen, Refund-Budget und neue Export-Snapshots
verwenden dieselbe Projektion. OP eines berechtigten Belegs rechnet alle
Zuordnungen ein, auch wenn ein komplettes mehrprojektiges Zahlungsobjekt für
den Leser verborgen ist. Keine Filterung des Rechnungsaggregats nach
Zahlungsobjekt-Sichtbarkeit. Alte Exportartefakte werden nicht umgeschrieben.

Quellenrest = ursprünglicher receipt-Betrag minus ursprüngliche und zusätzliche
positive Zuordnungen. Refunds geben dieses Budget nicht erneut frei. Zielrest
berücksichtigt dagegen sämtliche effektiven Zahlungen, Refunds und Gutschriften.
Der neue Betrag muss innerhalb derselben Transaktion beide Reste einhalten.
Bei installiertem Zusatzmodul prüft auch ein **neuer** `Finance.record_payment`
receipt-Befehl normale Rechnungszuordnungen gegen den effektiven OP-Rest.
Überschüsse können unzugeordnet bleiben. Historische Überzuordnungen und bereits
bestätigte Replays bleiben unverändert und werden nicht nachträglich ungültig.

## API und Datenformen

Pfadpräfix `/api/v1/business/accounting/allocations`. IDs 32 Kleinhexzeichen,
Hashes 64 Kleinhexzeichen, Beträge kanonische positive EUR-Centstrings gemäß
E1a, `reason` einzeilig 1–1000 Zeichen. Unbekannte Felder/Filter und doppelte
Queryparameter werden abgewiesen. Ein Fehler gespeicherter Quellen ist 409,
ungültige neue Eingabe 400, fehlende Rechte 403/404.

| Route | Inhalt |
| --- | --- |
| GET `/payments/{id}` | State der bereits übernommenen Zahlung |
| GET `/payments/{id}/candidates?limit=50&offset=0` | Berechtigte passende normale Rechnungen mit positivem Rest; nur Zielprojekte mit Schreibrecht, übliche E1a-Seitengrenzen |
| GET `/payments/{id}/history?limit=50&offset=0` | Bestätigte Einträge nach `revision DESC,id`; E1a-Seitengrenzen |
| POST `/payments/{id}/preview` | Side-effect-free Vorschau; kein Audit, keine Anfragequittung oder andere Schreibwirkung |
| POST `/payments/{id}/assign` | Ausdrückliche Bestätigung, 201, unveränderlicher Entry |

State: `{payment_id,event_id,source_hash,revision,state_hash,amount,currency:'EUR',
customer_id,allocated_amount,unallocated_amount,allocations,eligible,
blocked_reason,writes_allowed,scope:'authorized_sources',tax_result_available:false}`.
`revision` zählt Zusatzzuordnungen; anfangs 0. `customer_id` ist bei noch freier
ungebundener Zahlung null. `allocations` ist die aggregierte effektive Liste.
`state_hash` bindet ursprünglichen E1a-Quellenbeweis und alle eigenen
Zuordnungseinträge, getrennt vom unveränderten E1a-`source_hash`.
Gesperrte Fälle: `unsupported_payment`, `unsupported_source_documents`,
`missing_customer`, `mixed_customers`, `fully_allocated`, `overallocated`.
`writes_allowed` berücksichtigt aktuelle Rechte und Business-/Finanzmodul-/
Restore-Gates; keine neue steuerliche Freigabe.

Candidate: `{document_id,number,project_id,customer_id,buyer_name,gross,paid,
credited,open,payload_sha256,pdf_sha256,document_state_hash}`.
Der Zielhash bindet finale Beleg-/Archivnachweise und den effektiven Zahlungs-/
Gutschriftenstand; nur Dokumentrevision oder gerundeter OP genügen nicht.
Interne Nachweise dürfen erforderliche unveränderliche Quellenzeilen enthalten,
öffentliche Kandidaten dürfen keine fremden Zahlungs-IDs oder Gesamtbeträge
offenlegen. Listen enthalten `{items,total,next_offset,scope:'authorized_sources'}`.

PreviewBody: `{source_hash,expected_revision,state_hash,customer_id,document_id,
document_state_hash,amount,reason}`. Keine Anfrage-ID oder Bestätigung nötig.
Preview: `{payment_id,event_id,customer_id,source_hash,expected_revision,
state_hash,document,amount,reason,unallocated_before,unallocated_after,
open_before,open_after,preview_hash,scope:'authorized_sources',tax_result_available:false}`.
`document` ist der konkrete Candidate. Der Previewhash bindet die komplette
kanonische Vorschau ohne das Feld `preview_hash`. Vorschau verlangt zulässigen
aktuellen Schreibmodus, führt aber keine Schreibwirkung aus.

AssignBody: PreviewBody plus `{request_id,preview_hash,confirmation:true}`.
Entry: `{id,payment_id,event_id,revision,customer_id,source_hash,
previous_state_hash,document,amount,reason,unallocated_before,unallocated_after,
open_before,open_after,preview_hash,created_by,created_at,
scope:'authorized_sources',tax_result_available:false}`.
Eine Bestätigung ohne passende aktuelle Vorschau ergibt 409 ohne Teilwirkung.
Ein Konto muss für diese reine Zuordnung nicht mehr aktiv sein.

Gleiche Anfrage-ID und gleicher Inhalt liefern nach frischen Rechten,
Historienintegrität und Betriebsgates den gespeicherten Entry. Keine erneute
Prüfung historischer OP-Reste/Kandidatenzulässigkeit gegen spätere Vorgänge.
Neue Zuordnungen prüfen dagegen Quellenrevision/-hash, Zielhash, Kundenbindung,
Previewhash und beide Betragsgrenzen atomar. Fehler rollen Eintrag, Quittung
und Audit zurück. PostgreSQL nutzt die vorhandene globale Advisory-Lock;
SQLite die vorhandene IMMEDIATE-Transaktion und additive REPLACE-Guards.

Domainklasse `PaymentAllocations(office,clock=…)`: `state(actor,payment_id)`,
`candidates(actor,payment_id,limit=50,offset=0)`,
`history(actor,payment_id,limit=50,offset=0)`,
`preview(actor,payment_id,data)`, `assign(actor,payment_id,data)`.

## Restore und Clients

E1a-`restore_horizon` bleibt unverändert Version 1. Das neue Modul liefert
`restore_horizon(office)` als `{schema_version:1,table_counts:{alle_eigenen_Tabellen:Anzahl},sha256}`
über alle deterministisch sortierten eigenen Zeilen, einschließlich Requests.
`business_schema.financial_accounting_horizon(office)` liefert bei installiertem
Zusatzmodul ohne Komponentenmodul
`{schema_version:2,prejournal:<E1aH1>,allocations:<ZusatzH1>}`.
Ohne Zusatzmodul bleibt H1 bzw. None erhalten. Kein dynamischer OP im Restorehash.
Mit [E1b-2](CRM_ERP_EUER_E1B2_API.md#wiederherstellung-und-clients) ergänzt H3
den eigenen Komponentenstand; der hier beschriebene Teilhorizont bleibt erhalten.
Mit [E1b-3a](CRM_ERP_EUER_E1B3A_API.md#restorehorizont-und-historische-betreiberquittungen)
ergänzt H4 die Erstattungsursprünge; ohne Wiederverwendungsmodul verlangen neue
Freigaben dann Schema 5. Bei zusätzlich installiertem `business_accounting_capacity`
gilt der noch in Entwicklung befindliche, nicht freigegebene
[E1b-3b-Vertrag](CRM_ERP_EUER_E1B3B_API.md#horizonte-projektionen-und-nachweisgrenze):
H5/Schema 6 mit eigenem K1 über sechs neue Tabellen, auch bei leerem Modul.
Die äußeren Betreiberfelder und historischen Teilhorizonte bleiben unverändert.

Neue Betreiberfreigaben benötigen Schema 3 bei installiertem Zusatzmodul ohne Komponenten,
Schema 2 nur mit E1a, Schema 1 ohne Accounting. Schema 3 behält alle weiteren
Schema-2-Felder und externe Abgleichsbestätigungen. Ein exakt historisch bereits
bestätigter Schema-2-Bericht bleibt auch nach Migration wirkungsfrei quittierbar:
bekannte deklarierte Struktur, Betreiber-/Stopp-/Pending-/Restore-ID-Guards
und gespeicherter vollständiger Berichthash gelten weiter. Erst neue Freigaben
verlangen den aktuell vollständigen Umfang. Inspektion migriert niemals.

Browser/Flutter ergänzen bei übernommener Kundenzahlung „Rechnung zuordnen“.
Der Benutzer wählt eine Rechnung, bestätigt den angezeigten Kunden, Betrag und
Begründung, prüft die Vorschau und bestätigt gesondert. Danach werden Quellenrest
und OP neu geladen. Historischer E1a-Snapshot bleibt als solcher erkennbar.
Fehlendes Feature, offline, fehlende Rechte oder gesperrtes Finanzmodul verhindern
neue Befehle; verlorene Antworten verwenden denselben eingefrorenen Request.
Keine Änderung von Pending-Payloads und keine persistente neue Warteschlange.

## Betreibervertrag für Schema 3

Die gemeinsame reine Lesefunktion `financial_accounting_horizon(office)`
liefert bei installiertem Zusatzmodul ohne nachfolgende Komponentenmodule
genau diese Struktur:

```json
{
  "schema_version": 2,
  "prejournal": "unverändertes E1a-Horizontobjekt mit schema_version 1",
  "allocations": {
    "schema_version": 1,
    "table_counts": {
      "business_accounting_allocation_entries": 0,
      "business_accounting_allocation_requests": 0
    },
    "sha256": "64 Kleinhexzeichen des zusätzlichen Quellenstands"
  }
}
```

Der Platzhalter `prejournal` steht im echten JSON für das vollständige bisherige
Objekt, nicht für eine Zeichenkette. Beide Teilobjekte werden vollständig
verglichen. Es gibt keinen zusätzlichen Außenhash und keine Neuberechnung
historischer Zahlungsbeweise aus aktuellen OP-Beträgen. Eine teilweise
vorhandene Installation führt zum Fehler; sie wird nicht als leerer Zusatzstand
oder als alter E1a-Horizont ausgegeben.

Der vollständige Betreiberbericht verwendet `schema:3` und dieses Objekt als
`accounting_horizon`. Alle weiteren Felder und die private, unabhängige
Quellenprüfung entsprechen dem Schema-2-Vertrag. Auch ein installiertes leeres
Zuordnungsmodul ohne Komponenten verlangt für eine **neue** Freigabe Schema 3;
mit Komponenten ohne Erstattungsmodul ist Schema 4 erforderlich, mit
Erstattungsmodul ohne Wiederverwendungsmodul Schema 5; bei installiertem
Wiederverwendungsmodul Schema 6 nach dessen oben verlinktem Vertrag.
`--inspect` zeigt dafür `evidence_schema:3`; es erzeugt weiterhin keinen fertigen
Prüfbericht, keine Tabellen und keine Freigabe.

Bereits freigegebene Berichte werden zuerst entsprechend ihrer ausdrücklich
deklarierten bekannten Schemafassung geprüft. Bei unveränderter Restore-ID,
aufgehobener Finanzsperre und identischem gespeichertem Gesamthash bleibt ihre
Wiederholung wirkungsfrei, auch nach einer normalen additiven Migration.
Unbekannte Schemata, geänderte Berichte und neue Restore-IDs erlauben diese
Wiederholung nicht. Solange eine neue Finanzsperre besteht, ist anschließend
der komplette aktuell installierte Berichtsumfang erforderlich. Die bisherigen
PostgreSQL-Operator-/Writerstop- sowie lokalen Stopp-/Exklusivtransaktionsgrenzen
bleiben wirksam.

Die gezielten Nachweise stehen in
`backend/online/test_accounting_allocations_http.py`: E1a-H1 und Quellen bleiben
nach zusätzlicher Zuordnung unverändert; Schema-2-Altbericht übersteht eine echte
Migration als Quittungsreplay; neue Freigaben erkennen falsche oder unvollständige
Teilhorizonte; tatsächlicher Restore und CLI-Inspektion/Freigabe erhalten beide
Datenbereiche. Die SQLite-Zuordnungsfixture verwendet ausdrücklich den vorhandenen
synthetischen Rechnungsaussteller für Transport-/Restoremechanik. Die echte
Ausstellerpolicy und PostgreSQL-Rollentrennung sind gesonderte Integrationsnachweise.

Prüfstand 02.11.2026: **6 neue HTTP-/Operatorgrenztests**; zusammen mit den
bisherigen E1a-HTTP-/Restore-/Journey-, Backup-, Schema- und Portalrestorefällen
**47 Tests bestanden, keine übersprungenen Fälle**. Protokoll:
`work/verification/accounting-allocations-http-restore.log`.
