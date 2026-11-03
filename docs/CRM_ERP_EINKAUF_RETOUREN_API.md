# Vertrag: Belegte Bestelländerungen und Lieferantenretouren

Stand 03.11.2026, abgestimmter V1-Implementierungsvertrag. Feature
`purchase_changes`, Backend `business_purchase_changes`, relativer Businesspfad
`/purchasing/orders/{order_id}`. Zahlen als Dezimaltexte mit vier Nachkommastellen.

## Detail und Rechte

`GET /changes`:

```text
{
 id: order_id, order_id, project_id, supplier_name,
 source_revision, receipt_revision, amendment_revision, return_revision,
 source_sha256, financial_values_visible,
 confirmation: {order_reference, ordered_on, confirmed_by, confirmed_at} | null,
 items: [{line_index, article_id, article_name, article_code, unit,
          original_ordered_quantity, authorized_quantity,
          received_quantity, returned_quantity, retained_quantity, remaining_quantity}],
 receipts: [{id, order_id, project_id, source_revision, receipt_revision,
             receipt_reference, received_on, location_id, created_by, created_at,
             lines:[{line_index,article_id,article_name,unit,quantity,movement_id,
                     unit_cost_net?,cost_net?,returned_quantity,bound_quantity,
                     returnable_quantity,free_quantity,stock_value_net?}]}],
 amendments: [amendment_record], returns: [return_record], files: [file]
}
```

Lesen: `inventory.read` im wirklichen Bestellprojekt oder global bei projektloser
Bestellung. Änderungen zusätzlich `inventory.write` + `finance.approve`; Retouren
zusätzlich `inventory.write` + `finance.write`. Originalupload verlangt
`inventory.write` + `finance.write`; Download zusätzlich `finance.read`.
Finanzwerte erscheinen ausschließlich mit aktuellem `finance.read`. Detail/
History enthalten keine internen Quellenbeweise oder fremden Projektangaben.
Neue Writes verlangen aktives `organization.modules.material.enabled`;
akzeptierte Quittungen bleiben nach Deaktivierung bei frischen Rechten lesbar.

`file = {id,order_id,filename,media_type,size,sha256}`.
`POST /change-files`: `{request_id,filename,media_type,content_base64}`.
2 MiB pro Datei, höchstens 100 je Bestellung; PDF/PNG/JPEG/XML. Kein Überschreiben.
Ergebnis file mit Status 200. `GET /change-files/{id}/original` liefert Originalbytes.

## Gemeinsame Entscheidungsbasis

Alle Previews verlangen exakt:

```text
source_revision: detail.source_revision
expected_receipt_revision: detail.receipt_revision
expected_amendment_revision: detail.amendment_revision
expected_return_revision: detail.return_revision
source_sha256: detail.source_sha256
```

Plus die unten angegebenen Aktionsfelder. Ein Preview ist selbst keine Buchung.
HTTP POST des Previews hat keine request_id und kein confirmation-Feld.

`POST /amendments/preview` zusätzliche Felder:

```text
kind: quantity_change | replacement | cancel_remaining
reference: eindeutige externe Änderungsreferenz
 effective_on: YYYY-MM-DD
reason: begründete tatsächlich vereinbarte Änderung
 evidence_id: hochgeladenes Original dieser Bestellung
lines: [{line_index,authorized_quantity}]  // alle ursprünglichen Positionen genau einmal
```

Leerzeichen vor Feldnamen im Beispiel sind nur Formatierung. Mengen dürfen null,
aber nicht negativ sein; Menge nie unter bereits empfangener Bruttoliefermenge.
`cancel_remaining`: jede Menge exakt empfangen. `replacement`: keine Menge
verringern, mindestens eine erhöhen. `quantity_change`: mindestens eine wirkliche
Mengenänderung. Referenz/Grund/Original verpflichtend. Datum nicht vor Bestellung
oder nach heute. Artikel, Einheit, Lieferant und Projekt bleiben unverändert.

Previewergebnis:

```text
{order_id,action:'amendments',source_sha256,preview_sha256,
 values:{alle normalisierten Eingabefelder},
 lines:[{line_index,article_id,article_name,unit,received_quantity,
         previous_authorized_quantity,authorized_quantity,remaining_quantity}],
 financial_values_visible}
```

`POST /supplier-returns/preview` zusätzliche Felder:

```text
reference: eindeutige tatsächliche Rücksendereferenz
returned_on: YYYY-MM-DD
reason: tatsächlicher Rücksendegrund
 evidence_id: hochgeladenes Original dieser Bestellung
lines: [{receipt_id,line_index,quantity}] // mindestens eine, keine Duplikate
```

Mengen > 0. Eingangslager wird aus der originalen Lieferposition bestimmt, kein
frei erfundenes Ziellager/Projekt. Lagerbestand und Herkunftskapazität begrenzen
atomar die gesamte Auswahl; keine automatische Reservierungsauflösung.

Previewergebnis:

```text
{order_id,action:'supplier-returns',source_sha256,preview_sha256,
 values:{alle normalisierten Eingabefelder},
 lines:[{receipt_id,line_index,article_id,article_name,unit,location_id,
         quantity,received_quantity,returned_quantity,bound_quantity,
         returnable_quantity,free_quantity,stock_quantity,
         stock_value_net?,unit_cost_net?,book_value_net?,receipt_unit_cost_net?}],
 total_book_value_net?,financial_values_visible}
```

## Ausdrückliche Bestätigung und Quittung

`POST /amendments` bzw. `POST /supplier-returns` bekommt exakt die ursprünglichen
vollständigen Previeweingaben plus `{request_id, preview_sha256, confirmation:true}`.
Bei verlorenem Ergebnis dieselbe vollständige eingefrorene Eingabe und ID
wiederholen; keine neue Vorschau mit verändertem Auftrag unter alter ID senden.

Antwort Status 200:

```text
{order: detail_zum_Zeitpunkt_der_Annahme,
 record: amendment_record | return_record,
 financial_values_visible}
```

Gemeinsame Recordfelder: `id,order_id,project_id,revision,created_by,created_at,
source_sha256,source_revision,receipt_revision,amendment_revision,return_revision,
reference,reason,evidence_id,evidence_sha256,preview_sha256`.

Amendmentrecord zusätzlich `kind,effective_on,lines` mit unveränderten
Preview-Ausgabelinien. Returnrecord zusätzlich `returned_on,lines,total_book_value_net?`;
seine Lines tragen außerdem `id,sequence_number,after_movement_sequence,
after_adjustment_sequence`. Records sind flach, keine `values`-Verschachtelung.
Sie behaupten weder Lieferantenversand noch Zahlung oder EÜR-Wirkung.

Frische Rechte und unveränderte Originale werden vor akzeptiertem Replay geprüft;
heutige Quellen-/Revisiongleichheit erst bei neuer Fachwirkung. Finanzwerte werden
auch in ursprünglichen Quittungen anhand heutiger Leserechte ausgeblendet.
403/404: Zugriff entfernen. 409 `request_resolution=not_accepted`: sicher keine
Annahme unter dieser ID; andernfalls unklaren Auftrag erhalten. 423 neue Aktion
pausiert; ursprüngliche Werte und ID behalten. 413 Original/Transport zu groß.
400 bedeutet ungültige/fehlende Felder oder unerlaubten Kanal.

## Nativer Wareneingang nach Änderung

Bestehender `POST /receipts` bleibt kanonisch. Sobald eine Mengenänderung
vorhanden ist, muss der Auftrag zusätzlich `expected_amendment_revision` enthalten.
Der Wert wird im aktuellen `GET /purchasing/orders/{id}` additiv geliefert.
Die verbleibende Menge verwendet die aktuelle belegte Lieferfreigabe. Alte Clients
ohne Versionsbindung können danach keinen neuen Eingang buchen; alte bereits
angenommene Originalaufträge bleiben unverändert wiederholbar.

Clients sollen einen klaren Einstieg aus dem vorhandenen Bestelldetail bieten;
kein zweiter Bestellvorschlagseditor, keine automatische Finanzbuchung.
