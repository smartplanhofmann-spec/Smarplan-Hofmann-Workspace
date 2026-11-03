# Belegte Lieferantenretouren und Änderungen teilgelieferter Bestellungen

Stand: 03.11.2026. Konkreter Restbefund zu R07.02 und Entwurf für die nächste
additive Erweiterung. Dieser Bericht ist noch kein Implementierungs- oder
Prüfnachweis. Er baut auf Bestellung, Wareneingang, Lager, Inventur und
Geräteherkunft auf; diese Wege werden nicht neu aufgebaut.

## Geprüfte Ausgangslage

- `business_inventory.BusinessInventory.save_order` erlaubt Änderungen nur am
  Entwurf. Der freigegebene Vorschlag bleibt unveränderlich.
- `business_purchasing.Purchasing._confirmation` bindet dessen genaue Revision
  und Original-JSON. `receive` prüft Positionen gegen die ursprüngliche Menge,
  erzeugt echte `receive`-Lagerbewegungen und erhält originale Lieferungen.
- `business_stock_movements.kind=return` bedeutet ausschließlich die Rückgabe
  einer vorherigen Projektentnahme ins Lager. Dieser Weg kann keine Ware an den
  Lieferanten zurücksenden. Eine fingierte Projektentnahme würde Projektkosten
  erzeugen; ein fingiertes Lieferantenlager würde Ware weiter als eigenen
  Bestand führen. Beide Darstellungen sind fachlich falsch.
- `_stock` und der Integritätsreplay berücksichtigen bereits das additive
  Inventurjournal `business_inventory_adjustments`. Dessen Einträge sind durch
  `after_movement_sequence` zwischen native Lagerbewegungen eingeordnet.
- Reservierungen schützen den noch nicht entnommenen Bedarf. Gewichtet bewertete
  Entnahmen erzeugen Projektkosten; echte Projektrückgaben korrigieren diese
  zum historischen Entnahmewert.
- `business_asset_origins` bindet reale Geräte an Liefer- und Entnahmepositionen.
  Bereits gerätegebundene Entnahmemengen können nicht ins Lager zurückgebucht
  werden. Ein neuer Lieferantenretourenweg muss dieselbe Mengenkapazität in beide
  Richtungen schützen.
- Bestehende Einkaufsquittungen und Originalbelege dürfen durch neue aktuelle
  Projektionen nicht umgeschrieben oder nachträglich anders validiert werden.

## Begrenzter zusammenhängender Umfang

**Unveränderte Bestellung mit Teillieferung → Originalbeleg prüfen → tatsächliche
Lieferantenretoure oder dokumentierte Mengenänderung → aktuelle Restmenge und
freier Bestand → ausdrücklich vereinbarte Ersatz-/Restlieferung → Entnahme und
Geräteherkunft unter den verbleibenden Kapazitäten.**

Änderungen beziehen sich auf bestehende Positionsindizes derselben Bestellung,
denselben Artikel, dieselbe Einheit, denselben Lieferanten und dasselbe Projekt.
Artikelersatz oder ein anderer Lieferant verlangt einen neuen kanonischen
Bestellvorschlag, statt die Historie umzudeuten. Automatische Einheitenumrechnung,
Lieferanten-API, Nachrichten oder eine echte Bestellauslösung gehören nicht zu
diesem Abschnitt.

### Dokumentierte Bestelländerung

Eine Änderung enthält die aktuelle Quellen-/Liefer-/Änderungsrevision, externen
Änderungsbeleg, Referenz, Datum, Grund, Änderungsart und die ausdrücklich
freigegebenen Gesamtliefermengen je bestehender Position. Das ist die maximal
vereinbarte **kumulierte Bruttoliefermenge einschließlich belegter Ersatzlieferung**,
nicht eine nachträgliche Änderung bereits empfangener Ware.

- Eine Verringerung darf keine bereits tatsächlich empfangene Menge unterschreiten.
- Eine Stornierung offener Restmengen setzt die freigegebene Gesamtliefermenge
  auf die bereits empfangene Menge. Teilgelieferte Ware und Bestand bleiben.
- Eine zusätzliche Ersatzlieferung wird ausdrücklich als solche bezeichnet und
  erhöht die zulässige Gesamtliefermenge. Eine tatsächliche Retoure allein
  erzeugt keinen unbelegten Ersatzanspruch und öffnet die Bestellung nicht still.
- Empfangene Mengen bleiben Bruttolieferungen. Zusätzlich sichtbar sind
  zurückgesendete Menge, behaltene Menge und aktuell freigegebene Restliefermenge.
- Preise bereits empfangener Ware bleiben erhalten. Eine Mengenänderung erzeugt
  keine nachträgliche Neubewertung. Neue Wareneingänge verwenden weiterhin ihre
  ausdrücklich eingegebenen tatsächlichen Einstandspreise.

Beispiel: ursprünglich 10 Stück, 6 empfangen, 2 tatsächlich zurückgesendet.
Die Historie zeigt 6 empfangen, 2 retourniert, 4 behalten und weiterhin 4 offen.
Eine belegte Vereinbarung über 2 Ersatzstücke erhöht die kumulierte Lieferfreigabe
auf 12; dann sind 6 weitere Lieferungen zulässig. Stattdessen kann eine belegte
Reststornierung die Freigabe auf 6 senken: 0 offen, weiterhin 4 behalten.
Alle drei Größen bleiben sichtbar; die Software behauptet keine Zahlung oder
Gutschrift und versteckt keine bereits erfolgte Lieferung.

### Tatsächliche Lieferantenretoure

Eine Retoure verweist auf Bestellung, konkrete Wareneingangsposition(en), den
ursprünglichen Eingangslagerort, tatsächliches Rücksendedatum, Belegreferenz,
Grund und einen unveränderten Originalbeleg. Der Bediener bestätigt die wirkliche
physische Rücksendung; die Anwendung löst keinen Versand aus.

Vor der Bestätigung entsteht eine Vorschau mit Original-Liefermenge,
bereits zurückgesendeter und gerätegebundener Menge, freiem aktuellen Lagerbestand,
Reservierungen, gebuchtem Lagerwert und konkreter Ausbuchung. Alle Mengen werden
mit vier Nachkommastellen als Dezimaltexte verarbeitet. Die Bestätigung bindet
den gesamten frischen Quellenstand einschließlich Lagerbewegungen, Inventuren,
Retouren, Reservierungen und Geräteherkunft.

Eine Rücksendung muss gleichzeitig folgende Grenzen erfüllen:

1. Menge höchstens ursprünglicher Wareneingang minus bisherige Retouren minus
   daran gebundene Geräteherkunft.
2. Menge höchstens tatsächlicher freier Bestand im gewählten ursprünglichen
   Eingangslager; Reservierungen werden nicht still freigegeben.
3. Artikel und Einheit passen unverändert zur Lieferposition. Keine automatische
   Zuordnung von Transferketten, Seriennummern oder fremden Lieferungen.
4. Datum liegt nicht vor dem Eingang und nicht in der Zukunft. Die physische
   Rücksendung und Originalreferenz werden ausdrücklich bestätigt.
5. Eine Belegreferenz ist normalisiert je Bestellung eindeutig; gleiche
   Anfrage-ID ist wiederholbar, eine neue ID erzeugt keine zweite Buchung
   desselben Belegs.

Bereits entnommene, nicht gerätegebundene Ware muss bei einer tatsächlichen
Rücknahme zunächst den vorhandenen Projekt→Lager-Weg durchlaufen. Dieser allein
korrigiert die vorherigen Projektkosten. Bereits installierte gerätegebundene
Ware bleibt gesperrt; eine Gerätedemontage oder Aufhebung einer Herkunft wird
nicht aus einer Retoure erfunden. Das ist eine ausdrücklich sichtbare fachliche
Grenze, kein unsichtbares Überspringen der Herkunftskontrolle.

Der Artikelbestand ist ein gewichteter Bestand ohne automatische Chargenführung.
Die Zuordnung zur konkreten Lieferung ist eine ausdrückliche belegte
Bedieneraussage; sie wird nicht aus FIFO, Seriennummern oder Mengen allein
abgeleitet. Die verfügbare Kapazität bleibt dennoch hart begrenzt.

## Additive Tabellen und kanonische Lagerwirkung

Vorgeschlagenes Modul: `business_purchase_changes.py`, Feature
`purchase_changes`. Vorhandene Schemas/Checksummen und Originalzeilen bleiben
unverändert. Neue, ausschließlich appendierte Tabellen:

| Tabelle | Inhalt / verbindlicher Bezug |
| --- | --- |
| `business_purchase_amendments` | Bestellung, fortlaufende Änderungsrevision, ursprüngliche Quell-/aktuelle Lieferrevision, Art, Beleg, Datum, vollständige Positionsfreigaben, Grund, Hash und Autor |
| `business_purchase_receipt_terms` | Neuer Wareneingang → genau die bei Annahme gültige Änderungsrevision/Originalquelle; alte Eingänge bleiben implizit Revision 0 |
| `business_supplier_returns` | Tatsächlicher Rücksendevorgang, Bestellung, Referenzschlüssel, Datum, Beleg, Grund, frischer Quellhash, Autor |
| `business_supplier_return_lines` | Retoure → originale Wareneingangsposition, kanonischer Artikel/Lagerort, Menge, ausdrückliche Herkunft, abgeleiteter Lagerbuchwert, globale Retourenfolge und Journalgrenzen |
| `business_purchase_change_evidence` | Bestellgebundene unveränderte Originaldateien, MIME/Name/Größe/SHA-256; unterstützt auch projektlose Bestellungen |
| `business_purchase_change_requests` | Technische unveränderliche Anfragebindung und Originalquittung |

Für vorhandene projektgebundene Original-Lieferscheine bleibt
`business_delivery_documents` zuständig. Der neue Belegweg speichert den
Änderungs-/Retourenbeleg am tatsächlichen Bestellvorgang; er erzeugt keine neue
Rechnung und behauptet kein Dokument des Lieferanten ohne hochgeladenes Original.

Eine Lieferantenretoure wird ein eigenes kanonisches Ausbuchungsereignis mit
negativer Mengen-/Wertwirkung auf den bestehenden Lagerbestand. Die alte
CHECK-Beschränkung von `business_stock_movements` wird nicht mit einem falschen
Bewegungstyp umgangen und keine zweite Bestandsdatenbank aufgebaut. Wie die
vorhandenen Inventuranpassungen wird der additive Nachweis vom **gleichen**
Bestands-, Verfügbarkeits-, Reservierungs-, Entnahme- und Integritätsreplay gelesen.

Der aktuelle Lagerbuchwert wird gewichtet aus freiem/gesamtem tatsächlichem
Bestand abgeleitet; er ist nicht automatisch der Einkaufspreis dieser einen
Lieferposition oder der Wert einer späteren Lieferantengutschrift. Bei vollständiger
Ausbuchung wird der exakte verbleibende Wert übernommen, damit keine Rundungsreste
oder negativen Lagerwerte entstehen. Alle Positionen und ihre Quittung liegen in
einer serialisierten Transaktion; jede späte Störung verwirft den Gesamtvorgang.

### Reihenfolge mit Inventur ohne historische Umschreibung

Eine reine Referenz auf die letzte native Lagerbewegung reicht nicht: Zwischen
zwei Bewegungen können Inventur, Retoure und eine weitere Inventur stattfinden.
Deshalb speichert jede Retourenposition beide Grenzen:

- `after_movement_sequence`: zuletzt vorhandene native Lagerbewegung;
- `after_adjustment_sequence`: zuletzt vorhandene Inventuranpassung.

Der Replay verarbeitet je Bewegungsgrenze die Inventuranpassungen in ihrer
bestehenden Reihenfolge; Retouren werden jeweils **nach** der gespeicherten
Inventurgrenze und **vor** späteren Inventuren eingereiht. Mehrere Retouren an
identischen Grenzen folgen ihrer eigenen globalen, lückenlosen Sequenz.
Transaktionen verhindern eine Zwischenbuchung innerhalb eines mehrzeiligen
Vorgangs. Der Integritätscheck prüft monotone Grenzen, vollständige Folgen,
Mengen/Werte, Reservierungskapazität und den originalen Vorbestand.

Eine neue Retoure muss die Quellenbasis einer offenen Inventur verändern, selbst
wenn nach einer späteren anderen Bewegung zufällig wieder dieselbe Menge erreicht
wird. `InventoryCounts._basis` erhält daher den Hash der relevanten Retourenzeilen.
Alte eingefrorene Inventurbasen werden nicht umgeschrieben. Die Implementierung
muss ausdrücklich alte und neue Basen beim Restore unterstützen.

## Enge Änderungen vorhandener Wege

- `business_purchasing`: aktuelle Projektion der Mengenfreigaben, strikte
  Änderungsrevision bei neuen Lieferungen und atomare Autorisierungsbindung des
  Eingangs. Alte bestätigte Quellen bleiben exakt. Historische Prüfungen und
  Originalquittungen werden am damaligen Stand validiert, nicht am heutigen.
- `business_inventory`: bestehende `_stock`-/Integritätsrechnung um tatsächliche
  Lieferanten-Ausbuchungen ergänzen; Entnahme/Reservierung verwenden dadurch den
  aktuellen verminderten Bestand. Kein zusätzlicher Projektkostenposten.
- `business_inventory_counts`: Retourenquellen in neue Zählbasen aufnehmen;
  gemeinsame Journalreihenfolge sauber abgleichen.
- `business_asset_provenance`: verfügbare Lieferkapazität ist ursprüngliche Menge
  minus Retouren minus bereits gebundene Herkunft. Sowohl neue Herkunftsbindung
  als auch neue Retoure prüfen dieselbe Kapazität; Restore ebenfalls. Alte
  Geräte-/Lieferschein-/Entnahmeoriginale bleiben erhalten.
- Bestehende Finanz-, EÜR-, Bank-, Rechnungs- und Lohnjournale werden fachlich
  nicht verändert. Neue Originaltabellen in Exportkatalog/Datenschutzinventur,
  Registry, Paketlisten und Restore-/Runtime-Berechtigungen aufnehmen.

Veraltete Clients dürfen nach einer Mengenänderung keinen Eingang nur mit der
alten Vorschlags- und Lieferrevision buchen. Sobald eine Änderung existiert,
muss die aktuelle Änderungsrevision ausdrücklich im neuen Auftrag vorliegen.
Ein bereits angenommener älterer Eingang bleibt exakt wiederholbar, bei frischen
Rechten, bevor neue Versionsgleichheit geprüft wird.

## Vorgeschlagener API-/Rechtevertrag

Unter dem bestehenden Business-API-Stamm, keine Lieferantennetzwerkaufrufe:

| Methode / Weg | Zweck |
| --- | --- |
| `GET /purchasing/orders/{id}/changes` | Aktuelle Quellen, Mengenprojektion, Änderungs-/Retourenhistorie und Versionshash |
| `POST /purchasing/orders/{id}/change-files` | Unverändertes Original mit Anfrage-ID |
| `GET /purchasing/orders/{id}/change-files/{file}/original` | Berechtigter Originaldownload |
| `POST /purchasing/orders/{id}/amendments/preview` | Vollständige Mengenänderung anhand frischer Quellen prüfen |
| `POST /purchasing/orders/{id}/amendments` | Belegte externe Mengenvereinbarung ausdrücklich dokumentieren |
| `POST /purchasing/orders/{id}/supplier-returns/preview` | Tatsächliche mengen-/wert-/herkunftsgebundene Rücksendung prüfen |
| `POST /purchasing/orders/{id}/supplier-returns` | Rücksendeereignis und kanonische Bestandsausbuchung atomar bestätigen |

Lesen operativer Mengen/Historie: `inventory.read` im Bestellprojekt bzw. global
bei projektloser Bestellung. Originaldateien und Finanzwerte verlangen zusätzlich
`finance.read`; ein Lieferantenbeleg kann Preise enthalten. Mengenänderungen
verlangen `inventory.write` + `finance.approve`, Rücksendeausbuchung
`inventory.write` + `finance.write`. Sämtliche Zusatzrechte werden vor einem
angenommenen Replay erneut geprüft; aktuelle Leserechte bestimmen die erlaubte
Antwort. Kein alter Finanzsnapshot darf nach Rechteverlust zurückkehren.

Neue Aktionen benötigen ein aktives Materialmodul, ausdrücklich bestätigte
Vorschau und deren Hash. Ein akzeptierter Vorgang bleibt nach Moduldeaktivierung
bei aktuellen Rechten lesbar. Eindeutige Anfrage-ID, Instanz-/Sitzungsbindung,
Quellenstand, Originalbeleg und atomarer Persistenznachweis werden in beiden
Clients vor einer Wiederholung geprüft. Eigene bereits angenommene Bestandswirkung
darf das Lesen der ursprünglichen Quittung nicht blockieren.

## Projektkosten und EÜR

Eine Lieferantenretoure aus vorhandenem Lagerbestand ist keine Projektentnahme,
keine negative Rechnung, keine Zahlung und kein Lieferanten-Gutschriftbeleg.
Sie reduziert den Lagerbuchwert und die verfügbare Menge. Ein tatsächlicher
vorheriger Projekt→Lager-Rückgabevorgang korrigiert separat die ursprünglichen
Materialkosten; die anschließende Lieferantenretoure korrigiert diese Kosten
kein zweites Mal.

Eine echte Lieferantengutschrift bzw. Erstattung muss später als tatsächlicher
Finanzbeleg/Zahlung im vorhandenen Beleg-/Erstattungsweg erfasst und dort geprüft
werden. Retourenmengen, ursprünglicher Wareneingangspreis oder ein erwarteter
Erstattungsbetrag dürfen keine EÜR-, Umsatzsteuer- oder Bankbuchung erzeugen.
Beleg-/Steuerprüfung bleibt bei der Buchhaltung, nicht beim physischen Lagerjournal.

## Konkrete Abnahme vor Freigabe

1. Originalbestellung 10, Teilzugang 6, Reservierung 2: Rücksendung 5 abweisen,
   Rücksendung 2 nur aus freiem Bestand buchen; unveränderte ursprüngliche
   Bestell-/Lieferzeilen und exact-once Originalquittung nachweisen.
2. Ursprüngliche Lieferposition 3 und spätere andere Lieferung 7 zu anderem
   Preis: gewichtete Lagerausbuchung, verbleibender Wert und spätere Entnahmekosten
   stimmen; Artikelpreisänderung bewertet keine Historie neu.
3. Teilzugang 6, Retoure 2, explizite Ersatzfreigabe +2, zulässige Restlieferung
   bis kumuliert 12; Überlieferung und alter Änderungsstand werden atomar abgewiesen.
4. Teilzugang, belegte Reststornierung: bisherige Eingänge/Entnahmen/Geräte
   unverändert, Restmenge 0; kein fingierter Vollstorno gelieferter Ware.
5. Gerätemenge zuerst binden, dann Retoure versuchen und umgekehrt: gemeinsame
   Kapazität verhindert doppelte Verwendung; Projekt-Rückgabesperre bleibt.
6. Native Projektentnahme → tatsächliche ungebundene Rückgabe → Lieferantenretoure:
   Projektkosten genau einmal korrigiert, EÜR/Steuer-/Zahlungsjournale unverändert.
7. Native Bewegung → Inventur → Retoure → Inventur → Retoure → native Entnahme
   an derselben/folgenden Grenze: Wiederherstellungsreplay exakt, offene veraltete
   Inventur abgewiesen, kein negativer Bestand oder negative Reservierungsfreiheit.
8. Mehrere Positionen mit spätem Fehler, parallele identische/verschiedene
   Rücksendungen, Quittung nach Neustart, Rollen-/Projekt-/Finanzleserechtsverlust,
   deaktiviertes Materialmodul, beschädigter Originalbeleg und derselbe externe
   Beleg unter neuer Anfrage-ID.
9. Migration auf einer tatsächlichen Datenkopie mit vorherigen Einkaufsquittungen,
   Inventuren, finalisierter Rechnung/PDF und Geräteherkunft: ursprüngliche
   Tabellenfingerprints/Originale unverändert. Vollständiger PG-Dump/Restore,
   Runtime-ACL, SQLite-REPLACE-Schutz und Exportkatalog vollständig.
10. Browser und Flutter: reale Auswahl Originaleingang→Vorschau→Retoure→Restmenge,
    verlorene Antwort mit exakt gleichem Auftrag, Preisredaktion, Änderung nach
    Teillieferung, tatsächlicher Bestand und Gerätesperre; keine behauptete
    Lieferantenkommunikation oder automatische Erstattung.
