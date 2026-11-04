# Nächster Katalogvertrag: belegte Preisgültigkeit v2

Stand: 4. November 2026. Dieses Dokument bewahrt den ursprünglichen Erweiterungsplan. Der daraus implementierte Vertrag, einschließlich Abweichungen und Prüfstand, steht in [CRM_ERP_KATALOG_PREISE_V2_API_2026-11-04.md](CRM_ERP_KATALOG_PREISE_V2_API_2026-11-04.md). Backend, Browser und Native sind umgesetzt und unabhängig nachgeprüft; die gemeinsame Integration im Hauptrepository wird gesondert geprüft. CSV v1 und DATANORM A14 bleiben unverändert.

Grundlage sind `CRM_ERP_Gesamtziel.txt`, Abschnitt 7, und die Gegenprüfung `CRM_ERP_GESAMTZIEL_GEGENPRUEFUNG_2026-11-04.md`, Abschnitt 2. Das Gesamtziel verlangt erkennbare Preisgültigkeit; die Gegenprüfung konkretisiert die Bindung von Angebot und Bestellung an eine ausdrücklich gewählte gültige Preisrevision. Konkrete Lieferantenformate und direkte Schnittstellen sind weiterhin offen. Der folgende CSV-Vertrag ist deshalb ein **eigenes Smartplan-Format**, keine behauptete Lieferantenspezifikation.

## Tatsächlicher Ausgangspunkt und Folgerung

`business_adapters.parse_catalog/import_data/apply_catalog` speichert und übernimmt aktuelle Artikelwerte. Der neue `CatalogImports.preview` zeigt die tatsächliche V1-Entscheidung samt identischem-Quellhash-No-op. Keiner dieser Verträge besitzt zeitliche Preisquellen. Sie werden nicht rückwirkend umgedeutet.

`Documents.save_article` und `business_article_versions` halten Artikelrevisionen fest. `Documents._positions` verlangt für eine neue Artikelposition deren aktuelle Revision und übernimmt danach einen Snapshot. `business_pricing.preview` verwendet ebenfalls aktuelle Artikelrevisionen. `BusinessInventory.save_order` speichert Bestellpositionen; `Purchasing.confirm` friert die Quelle der extern erteilten Bestellung ein. `Purchasing.receive` verlangt tatsächliche Einstandspreise. Lagerabgänge werden aus dem Lagerjournal bewertet. Das sind unterschiedliche fachliche Quellen: Ein neuer Lieferantenkatalog darf weder alte Belege noch vorhandene Lagerwerte nachträglich ändern.

Der kleinste vollständige v2-Umfang muss daher **Preisquellen importieren und auswählen**, nicht bloß neue Datumsfelder an den aktuellen Artikelpreis hängen. Ein zukünftiger Preis wird gespeichert, ohne den gegenwärtigen Artikelpreis sofort zu ersetzen. Ein abgelaufener oder mehrdeutiger Preis wird nicht still als aktueller Preis benutzt.

## Vorgeschlagener eigener CSV-v2-Vertrag

Eine Zeile beschreibt genau **eine Preisrolle für einen Artikel und einen Gültigkeitszeitraum**. Einkauf und Verkauf dürfen dadurch unterschiedliche Zeiträume haben. Vorschlag für die exakte Kopfzeile:

```text
price_id;code;name;unit;price_role;price_net;price_base_quantity;currency;tax_rate;valid_from;valid_until
```

| Feld | Verbindlicher vorgeschlagener Vertrag |
| --- | --- |
| `price_id` | Nicht leere externe Preiskennung innerhalb dieser Katalogquelle. Dieselbe Kennung bezeichnet dieselbe fachliche Preisquelle; eine Korrektur ist eine ausdrücklich ersetzende Revision. |
| `code`, `name`, `unit` | Artikelnummer und Stammdatenbehauptung des Originals. Keine automatische Zusammenführung gleicher Nummern aus verschiedenen Quellen. Die belegfähige Einheit muss die vorhandene Fachgrenze erfüllen; keine bloß syntaktische Akzeptanz unbenutzbarer Einheiten. |
| `price_role` | Ausschließlich `purchase_net` oder `sales_net`. Einkaufspreise werden niemals automatisch zu Verkaufspreisen. |
| `price_net` | Nicht negativer EUR-Nettobetrag als Dezimaltext mit höchstens vier Nachkommastellen. Ein ausdrücklich angegebener Nullpreis ist gültig; Leerwert ist kein Nullpreis. |
| `price_base_quantity` | Ausdrücklich positive Bezugsmenge mit höchstens vier Nachkommastellen. `12.00` EUR pro `100` Stück bleibt genau diese Preisbasis. Keine vorgezogene, verlustbehaftete Umrechnung in einen gerundeten Stückpreis. |
| `currency` | Zunächst ausschließlich `EUR`, entsprechend dem bestehenden Belegvertrag. Fremdwährungen werden abgelehnt; kein erfundener Wechselkurs. |
| `tax_rate` | Ausdrückliche Rate aus dem eigenen Format, 0 bis 100. Die Preisquelle ersetzt nicht die steuerliche Prüfung der konkreten Belegposition. Die bestehenden Kategorie-/Befreiungsregeln bleiben verbindlich. |
| `valid_from` | Erforderliches echtes Kalenderdatum `YYYY-MM-DD`; kein Dateiname, Uploadzeitpunkt oder Serverdatum als Ersatz. |
| `valid_until` | Echtes Kalenderdatum oder leer für **ausdrücklich ohne Enddatum**. Ein fehlender Beginn ist weiterhin unzulässig; „unbekannt“ wird nicht zu „unbegrenzt“. |

UTF-8, optionaler BOM, Semikolon, höchstens 2 MiB/2.000 Zeilen sowie dieselbe sichere Text-/Dezimalbehandlung wie beim eigenen v1. Mehrere Zeilen derselben Artikelnummer sind in v2 möglich, sofern Preisrolle/Gültigkeit eindeutig bleiben. Doppelte `price_id` innerhalb einer Datei werden abgelehnt, auch bei identischen Werten.

**Offengelegte Produktentscheidungen dieses Vorschlags:** Beide Datumsgrenzen sind einschließlich. Der 30.11. gehört also noch zum alten Preis; der 01.12. kann direkt den neuen Preis beginnen. Datumswerte sind fachliche Kalendertage, keine impliziten UTC-Zeitpunkte. Leer `valid_until` bedeutet ausdrücklich offene obere Grenze. Diese Regeln gehören in Formatbeschreibung und beide Clients. Sie sind keine aus einer noch unbekannten Lieferantenquelle abgeleitete Rechtsannahme.

Zusätzlich zur Datei wird eine belegte Katalogreferenz/Quellrevision erfasst. Eine bereits verwendete Quellrevision mit anderem Originalhash wird als Widerspruch abgelehnt. Uploadzeit, Originalhash und Bediener bleiben separate Provenienzdaten; sie bestimmen keine Preisgültigkeit.

## Additive Speicherung und eindeutige Übernahme

Ein eigenes Modul, beispielsweise `business_catalog_prices`, erhält eine neue Migration mit unveränderlichen Originalen, Preisrevisionen, Artikelbindungen, ausdrücklichen Ablösungs-/Korrekturereignissen und Requestquittungen. Die eingefrorenen v1- und Originalmodulschemata werden nicht erweitert. Der neue Domainpfad sollte getrennt sein, beispielsweise `/catalog-prices/...`; die Katalogoberflächen führen v1/v2-Quellen zusammen. Dadurch kann ein alter Client v2 nicht versehentlich über die v1-Annahme ausführen.

Jede angenommene Preisrevision bindet mindestens Quelle/Katalogrevision, `price_id`, tatsächlichen Original-/Positionshash, Artikel-ID und Artikel-/Bindungsrevision, Preisrolle, Betrag/Basis/Einheit/Währung, Gültigkeit, Korrekturvorgänger, fachlichen Hash und Annahmeauftrag. Der Zeitstempel der Annahme ist zusätzlich zur fachlichen Gültigkeit zu speichern.

Die Vorschau entscheidet pro Zeile über Neuanlage, identische Wiederholung, Preisrevision, Stammdatenabweichung, Einheitkonflikt und Gültigkeitskonflikt. Sie bindet den vollständigen aktuellen Stand der betroffenen Preisquelle und Artikelbindung. Die Annahme prüft diesen Stand atomar erneut und schreibt ausschließlich die bestätigten Entscheidungen. Identischer Request wird mit derselben Quittung wiederholt; gleicher Request mit anderen Werten wird abgelehnt.

Bei gleicher Quelle, Artikelbindung und Preisrolle darf zum gewählten Tag höchstens eine aktive angenommene Preisrevision gelten. Überlappungen sind ein Konflikt; weder Uploadreihenfolge noch höchster Preis noch neuestes Datum entscheiden still. Eine Korrektur nennt ausdrücklich die ersetzte Preisrevision und erwartet deren Hash. Der ersetzte Fakt bleibt lesbar und in alten Belegsnapshots gebunden. Erst die neue aktive Auswahl berücksichtigt die korrigierte Revision.

Einheiten werden nicht durch Preisimporte umgedeutet. Passt die neue Einheit nicht zur Lageridentität, muss der Nutzer ausdrücklich einen neuen Artikel beziehungsweise eine passende bestehende Artikel-ID wählen. Eine Konvertierung zwischen Packung/Stück oder `ST`/`C62` wird nicht geraten. `price_base_quantity` beschreibt nur die Preisbasis derselben bestätigten Einheit. Ein späteres Konvertierungsmodell wäre ein eigener belegter Vertrag.

V1-Quellen bleiben als „Gültigkeit nicht angegeben (v1)“ sichtbar. Eine Überführung in v2 verlangt eine neue ausdrücklich datierte Preisquelle mit Originalbezug. Frühere v1-Quittungen erhalten weder erfundene Gültigkeitsdaten noch nachträgliche v2-Bindungen.

## Preiswahl in Angebot, Kalkulation und Bestellung

Die Auswahl erhält eine ausdrückliche `effective_on`-Angabe, Preisrolle, Artikel-ID und Quellwahl. Bei mehreren Lieferanten ist die Lieferanten-/Katalogquelle ebenfalls ausdrücklich zu wählen. Antwortzustände sind mindestens `eligible`, `not_yet_valid`, `expired`, `missing_validity`, `overlap` und `unit_conflict`. Es gibt keinen automatischen Rückfall auf eine andere Rolle, Quelle oder einen undatierten Artikelpreis.

Ein bestätigter Preisnachweis enthält Preisrevision/Hash, Auswahlstichtag, Betrag, Basis, Einheit, Rolle und Originalbezug. Angebot und Bestellung speichern diesen vollständigen Snapshot. Bei einer neuen Bestätigung müssen Quellrevision und Datum noch zum überprüften Stand passen. Ein neuer Katalog darf bestehende bestätigte Angebote, Aufträge, Bestellungen oder Lagerbuchungen nicht neu berechnen.

Konkrete erforderliche Integrationspunkte:

1. `Documents._positions`: Neue v2-bezogene Artikelpositionen übernehmen ausdrücklich gewählte Verkaufspreisquellen; die bestehende `price_base_quantity` bleibt im Snapshot erhalten. Ein Wechsel des relevanten Stichtags invalidiert die neue Vorschau. Bereits gespeicherte historische Positionen behalten ihren eigenen gebundenen Stand.
2. `business_pricing.preview` und `snapshot_matches`: Ausdrücklich gewählte Einkaufspreisquellen für Kosten-/Stücklistenbasis binden, einschließlich Bezugsmenge. Der nachgelagerte bestehende Rundungsablauf bleibt unverändert. Eine Quellpreisdivision wird nicht bereits beim Import auf vier Nachkommastellen abgeschnitten.
3. `BusinessInventory.save_order` und `Purchasing.confirm`: Einkaufspreisquelle samt Preisstichtag im Bestellvorschlag und anschließend im bestätigten Bestellsnapshot binden. Quellenwechsel zwischen Vorschau und Bestätigung ergibt 409.
4. `business_sales`-Übernahmewege: Der gegenwärtige Direktweg vom Artikel zum Angebotspositionssnapshot muss dieselbe Auswahl verlangen; andernfalls könnte er eine fehlende Preisgültigkeit umgehen.
5. `BusinessInventory.movement` und `Purchasing.receive`: Tatsächliche Zugangskosten bleiben ausdrücklich tatsächliche Werte. Bei einer v2-preisgeführten Artikelquelle darf eine fehlende tatsächliche Kostenangabe nicht still auf einen Platzhalter im Artikelstamm fallen. Abgänge und Rückgaben bleiben auf dem bestehenden Lagerjournal beziehungsweise historischen Ursprungsbeleg.
6. Browser- und native Artikel-/Beleg-/Bestelleditoren: Gleiche Auswahlstichtage, Konfliktanzeigen, Quellenbindungen und ausdrücklich angezeigte Preisbasis. Alte Clients müssen einen verständlichen fachlichen Fehler erhalten, wenn für einen v2-preisgeführten Artikel die neue Quellenbindung erforderlich ist.

Für neu angelegte v2-Artikel darf ein technischer Nullwert im alten Artikelpreisfeld nicht versehentlich zu einem verwendbaren Nullpreis werden. Vor Freigabe der neuen Artikel sind daher die genannten Serverprüfungen vollständig erforderlich. Ein v2-Artikelpreis wird entweder ausdrücklich datiert ausgewählt oder unabhängig und begründet als tatsächlicher Einzelpreis erfasst. Diese Auswahlzustände müssen im Datenmodell unterscheidbar sein; ein implizites „heute“ löst das Problem nicht.

## Unabhängig erwartete Grenzfälle

| Fall | Erwartetes fachliches Ergebnis |
| --- | --- |
| 10 EUR gültig bis einschließlich 30.11.; 12 EUR ab 01.12. | Auswahl 30.11. = 10; Auswahl 01.12. = 12. Novemberangebot bleibt nach Dezemberimport unverändert auf 10. |
| Upload am 04.11., Preis erst ab 01.12. | Gespeicherte zukünftige Quelle; keine sofortige Ersetzung des Novemberpreises. |
| Zweite Quelle derselben Rolle bereits ab 30.11. | Konflikt am 30.11.; keine stille Tages-/Uploadpriorität. |
| Alter Preis ohne Ende, neuer Preis ab 01.12. | Überlappung bis die Ablösung ausdrücklich bestätigt ist; keine automatische Verkürzung des Originals. |
| Lücke am 01.12.; nächster Preis erst am 02.12. | `expired` beziehungsweise keine gültige Auswahl am 01.12.; kein Rückfall auf November. |
| V1-Artikelpreis 10 EUR ohne Gültigkeit | Als undatiert sichtbar, keine automatische v2-Auswahl. |
| 1 EUR pro 3 Stück, Angebotsmenge 3 | Genau 1 EUR netto vor nachgelagerten Belegregeln; kein Import von 0,3333 EUR mit späterem Ergebnis 0,9999 EUR. |
| 12 EUR pro 100 Stück, Mengeneinheit Stück | Preisbasis 100 bleibt im Angebot/Bestellnachweis sichtbar. „100“ erzeugt keine Packungseinheit. |
| Nullpreis ausdrücklich belegt versus leeres Preisfeld | Nullpreis gültig; Leerpreis Fehler, kein erfundenes `cost_known=true`. |
| Änderung Stück zu Packung bei bestehender Lagerhistorie | Vorschau blockiert Umdeutung; ausdrücklicher neuer Artikel möglich, alte Lagerbewegungen bleiben unverändert. |
| Gleiche Artikelnummer in zwei Lieferantenquellen | Zwei Herkunftsquellen, ausdrückliche Bindung; kein automatisches Zusammenführen. |
| Gleiche Datei/Request nach verlorener Antwort | Dieselbe Original-/Preis-/Annahmeidentität, keine zusätzlichen Revisionen. |
| Gleiche Quellrevision mit geändertem Original oder Vorschau nach Fremdänderung | Konflikt; keine teilweise Preisübernahme. |
| Historische Preisrevision wird später korrigiert | Alte Belege bleiben an der alten Revision; neue Auswahl zeigt die ausdrücklich korrigierte Quelle. |
| Jahreswechsel/Schalttag/31.04./ab größer bis | Echte Kalenderprüfung; keine Zeitzonenverschiebung oder still normalisierte ungültige Daten. |
| Rechteverlust/Moduloff/Background während Original/Preview/Annahme | Keine wiedererscheinenden privaten Dialoge; unklare Annahme bleibt mit unverändertem Auftrag wiederholbar. |
| Export/Backup/Restore mit Original, Korrektur und altem Novemberbeleg | Alle Bytes, Quellenrevisionen, Artikelbindungen und November-Snapshots bleiben gleich; Integritätsfehler sperren die Wiederfreigabe. |

## Kleinste sinnvolle Umsetzungsreihenfolge

1. Eigenes v2-Domänenmodul mit Parser, Originalen, gebundenen Artikelentscheidungen, datierten Preisrevisionen, read-only Auswahl, expliziter Ablösung und strengen Konflikten. Alte v1-Regressionsquittungen unverändert gegenprüfen.
2. Beide Katalogclients auf genau diesen Serververtrag setzen; keine nachgebaute clientseitige Gültigkeits-/No-op-Entscheidung. Original-/Historien-/Replay-/Lifecycle-Gegenfälle übernehmen.
3. Die oben genannten Beleg-, Kalkulations-, Bestell- und Direktübernahmewege vollständig anbinden. Erst danach v2-preisgeführte neue Artikel zur Verwendung freigeben. Konkreter November/Dezember-Ablauf in Browser und nativ einschließlich alter Belege.
4. SQLite und PostgreSQL, tatsächliche HTTP-/MFA-Flows, getrennte Runtime-Rechte, Export und tatsächlicher Restore in einer neuen reservierten Testziel-Datenbank prüfen. Paketlisten/Releaseinventar und beide Client-Vertragsfixtures vervollständigen.

Offen bleiben externe Lieferantenbelege für konkrete Datums-/Preisrollen, Rabatt-/Staffel-/Währungsmodelle und echte Lieferantenformatabnahmen. Diese werden nicht aus dem eigenen CSV-Vertrag als bereits bewiesen abgeleitet. Für den beschriebenen eigenen CSV-v2-Kern sind keine erfundenen Anbieterzugänge erforderlich.
