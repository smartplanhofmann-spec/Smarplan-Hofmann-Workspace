# Unabhängige Gegenprüfung von Bestelländerungen und Lieferantenretouren

Stand 03.11.2026, abgeschlossener interner Review des geprüften Vertrags aus
[CRM_ERP_EINKAUF_RETOUREN_API.md](CRM_ERP_EINKAUF_RETOUREN_API.md).
Geprüft werden das neue Backend sowie seine engen Verbindungen zu nativen
Wareneingängen, Lagerbewegungen, Inventur und Geräteherkunft. Kein Anbieter,
Lieferant, produktiver Bestand oder Zahlungsdienst wurde angesprochen. Die
PostgreSQL-Abnahme des Implementierungsagenten wurde nicht verändert.

Die unabhängigen Fälle stehen in
[test_business_purchase_changes_review.py](../backend/test_business_purchase_changes_review.py).
Sie verwenden tatsächlich beschriebene temporäre SQLite-Datenbanken und
die kanonischen Fachbefehle; vorhandene Tests werden nicht durch Vererbung
als zusätzliche eigene Fälle mitgezählt.

## Bestätigte Funktionsgrenzen

- Zwei Bestellpositionen desselben Artikels teilen sich einen Lagerbestand.
  Zwei Rücksendemengen von jeweils vier sind bei sechs freien Einheiten
  zusammen gesperrt. Zwei Mengen von jeweils drei werden mit insgesamt
  18,0000 EUR bewertet; vier reservierte Einheiten bleiben unangetastet.
- Die Kapazität der ursprünglichen Lieferpositionen bleibt getrennt. Eine
  Position mit drei gelieferten Einheiten kann trotz sieben weiterer Einheiten
  desselben Artikels keine vierte Einheit zurücksenden. Ein späterer anonymer
  Zugang desselben Artikels erneuert diese Herkunftskapazität ebenfalls nicht.
- Ein späterer Wareneingang zu einem anderen Preis verändert die aktuelle
  Durchschnittsbewertung. Die früher bestätigte Retoure, der alte Wareneingang
  und die ursprüngliche Bestellbestätigung bleiben exakt wiederholbar.
- Die Folge Wareneingang → Inventur → Retoure → Umlagerung → Inventur → Retoure
  → Rückumlagerung → Projektentnahme → Retoure wird in tatsächlicher Reihenfolge
  geprüft. Bestand im anderen Lager ersetzt keinen Bestand am ursprünglichen
  Eingangslager. Die Projektentnahme erzeugt genau 4,00 EUR Materialkosten;
  Lieferantenretouren verändern diesen Betrag nicht. EÜR-, Finanz- und
  Banktabellen bleiben inhaltlich unverändert.
- Zulässige Eingaben mit führenden Dezimalnullen oder äußeren Textleerzeichen
  bleiben als exakter Originalauftrag erhalten und werden fachlich normalisiert
  dargestellt. Mehrdeutige Base64-Paddingbits werden vor Annahme eines Originals
  abgewiesen; es entsteht dadurch keine später nicht prüfbare Dateiannahme.

## Reproduzierte und geschlossene Integritätsbefunde

Nach echter Lieferung von sechs und Rücksendung von zwei Einheiten wurde in
einer synthetischen beschädigten Sicherung ausschließlich die gespeicherte
Quittungsansicht `result_json.order.items[0].received_quantity` auf `999.0000`
gesetzt. Der eigene `result_sha256` wurde neu berechnet. Das Modell setzt einen
Betreiberzugriff voraus, der den unveränderlichen SQL-Guard bewusst entfernt;
die normale Runtime erhält diese Möglichkeit nicht.

Die Gesamtintegritätsprüfung akzeptierte den Widerspruch zur unveränderten
Fachquelle. Das alte Replay konnte entsprechend eine falsche historische
Bestellansicht zurückgeben. Die negative Gegenprobe war tatsächlich rot:
`work/verification/purchase-changes-independent-initial.log`, drei Fälle in
0,971 s, davon dieser eine fehlgeschlagen. Der zusätzliche echte Umlagerungs-/
Inventurfall bestand separat in 0,421 s.

Der Befund wurde dem Implementierungsagenten und dem Integrationsverantwortlichen
mit Reproduktion gemeldet und korrigiert. Die Korrektur rekonstruiert die komplette damalige
Bestellansicht aus Originalquelle, damaligen Receipt-/Änderungs-/Retourenpräfixen
und gebundenen Journalgrenzen. Die nachgezogene Gegenprobe ist sowohl für den
Restorevalidator als auch für akzeptierte Replays grün. Heutige Lagerwerte
werden dabei nicht als alte Quittungswerte verwendet.

Bei der Nachsicht wurde ein zweiter eng verwandter Widerspruch reproduziert:
Wurde nur der gespeicherte Originalauftrag auf `confirmation:false` geändert
und sein eigener Hash erneuert, akzeptierten Restore und Replay diese fachlich
unmögliche ursprüngliche Annahme. Der Befund und seine Gegenprobe liegen
unter `work/verification/purchase-changes-independent-followup.log`: fünf Fälle
in 1,887 s, davon dieser eine mit zwei fehlgeschlagenen Unterprüfungen.
Die Korrektur bindet jetzt den exakten Feldumfang, die ausdrückliche Bestätigung,
typisierte Quellversionen, Datum, Art, Originalbeleg, normalisierte Referenz und
Grund sowie sämtliche eindeutigen Mengenpositionen an den angenommenen Record.
Dies wird sowohl vor akzeptiertem Replay als auch beim Restore geprüft.
Ein zusätzlicher positiver Fall erhält dabei die
legitime Unterscheidung zwischen exaktem Originalbody (`02.0000`, äußere
Leerzeichen) und normalisierter Fachansicht (`2.0000`, bereinigte Texte).
Beide negativen Unterprüfungen sind nach der Korrektur grün. Der ursprüngliche
Auftrag wird nicht durch eine neu formatierte Eingabe ersetzt.

## Abschließende Nachweise

Der unabhängig ausgeführte gemeinsame Lauf bestand **96/96 in 23,397 s**, ohne
Skip: sieben eigene Gegenproben, 13 neue Domainfälle, zwei echte lokale
HTTP-Fälle sowie 74 bestehende Einkaufs-, Lager-, Inventur- und
Geräteherkunftsfälle. Protokoll:
`work/verification/purchase-changes-independent-final.log`.

```sh
PYTHONPATH=backend:backend/online /tmp/smartplan-backend-verified/bin/python -m unittest \
  test_business_purchase_changes_review test_business_purchase_changes \
  test_business_purchase_changes_transport test_business_purchasing \
  test_business_inventory test_business_inventory_counts \
  test_business_asset_provenance -v
```

Der Implementierungsagent führte anschließend die echte PostgreSQL-Abnahme
nach beiden Korrekturen aus: **3/3 in 13,732 s**, ohne Skip. Code und Protokoll
`work/verification/purchase-changes-pg.log` wurden unabhängig gelesen. Die
Fälle umfassen MFA/HTTP, konkurrierende identische Retouren, frische Rechte und
Runtime-/Owner-SQL-Guards; tatsächliches Dump/Restore mit unveränderter
finalisierter Rechnung/PDF; sowie die additive Migration eines vorherigen
PG-Stands mit bereits vorhandenen Lieferungen, Inventur und Rechnung.

Der zusätzlich gelesene breitere Implementierungslauf bestand **118/118 in
28,617 s** (`work/verification/purchase-changes-regression.log`). Diese Mengen
überschneiden sich mit dem unabhängigen Lauf und werden nicht addiert. Alte
Quelltabellen und native Bestell-/Wareneingangsquittungen behalten ihre
bisherigen Inhalte. Die neuen historischen Beweise ergänzen nur den neuen
Einkaufsänderungsbereich um Journalgrenzen und Quellenprüfung.

Im geprüften Umfang bleibt kein offener Befund aus diesem Review. Physische
Rücksendung, eine tatsächliche Lieferantengutschrift oder eine Zahlung werden
weiterhin nicht durch das Lagerjournal behauptet oder ausgeführt. Dieser
Backendnachweis ersetzt keine gerätespezifische Nutzerabnahme der Clients.

Die zusätzliche lesende Prüfung der Datenschutzquellen bestätigte die frische
Inventar-/Finanzberechtigung und tatsächliche Projektzuordnung über Bestellung,
Wareneingang beziehungsweise Retoure. Unklassifizierte vollständige
Betriebsmittelhistorien bleiben der Geschäftsführung vorbehalten. Daraus wird
keine automatische vollständige Personenauskunft abgeleitet.
