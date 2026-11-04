# CSV-v2: datierte Preise in Belegen und Kalkulationen

Stand: 04.11.2026. Implementierter und lokal geprüfter Consumerbaustein im Arbeitsbaum `/workspace/smartplan-catalog-prices-v2-20261104`. Er benötigt die dort parallel entwickelte Domäne `business_catalog_prices`; er ist keine eigenständige Freigabe des gesamten V2-Pakets. CSV-v1-Speicherverträge und vorhandene Originale/Preisquittungen werden nicht umgeschrieben.

## Belegposition und CRM-Angebotsübernahme

Eine neue Position eines V2-preisgeführten Artikels benötigt `article_id`, aktuelle `article_revision`, `quantity` und ausdrücklich:

```json
{"catalog_price_selection":{"price_id":"<32hex>","price_revision":1,"price_sha256":"<64hex>","effective_on":"2026-11-30"}}
```

`unit_price_net`, `price_base_quantity` und `unit` können bei der Übernahme entfallen. Falls der Aufrufer sie mitsendet, müssen sie dem gewählten Verkaufspreis entsprechen; ein alter technischer Nullwert oder früherer V1-Preis führt zu 409. Der Server speichert die vollständigen Originalfakten als `catalog_price_snapshot`. Ein mitgeschickter Snapshot allein berechtigt keine neue Position, auch nicht mit einer selbst vergebenen Positions-ID.

Der Preisbetrag bleibt zusammen mit seiner tatsächlichen Bezugsmenge erhalten: `1.00 EUR / 3 ST` bei Menge `3 ST` ergibt vor den vorhandenen Steuerregeln genau `1.00 EUR`. Es wird kein gerundeter Stückpreis importiert. Der gewählte Preisstichtag ist eine ausdrückliche fachliche Angabe und wird weder durch Uploadzeit noch durch die Serveruhr ersetzt.

Die Steuer aus dem Preisoriginal dient als Anfangswert. Eine ausdrücklich andere Belegsteuer bleibt nach den bestehenden Kategorie-/Befreiungsregeln zulässig: beispielsweise `tax_rate: "0"`, `tax_category: "AE"` und ein ausdrücklich erfasster Befreiungsgrund. Der Snapshot zeigt weiterhin unverändert die ursprüngliche Katalogsteuer; er behauptet keine steuerliche Freigabe der konkreten Leistung. Betrag, Bezugsmenge und Einheit bleiben strikt gebunden.

Automatische Einstandskosten aus dem technischen Artikelstamm werden für preisgeführte Artikel weggelassen, auch wenn dort manuell ein älterer Wert steht. Eine ausdrücklich in der Belegposition eingegebene tatsächliche Kostenangabe bleibt nach dem bisherigen Vertrag möglich. Ohne eine solche Kostenangabe weist die Angebotskalkulation unbekannte Kosten aus.

`Sales.adoption(..., kind="offer")` akzeptiert dieselbe optionale `catalog_price_selection` je ausgewähltem Artikel und übergibt Artikel-ID und Revision an `Documents.create`. Damit entfällt der bisherige Kopierweg, der nur aktuelle numerische Artikelwerte ohne Herkunft übernahm. Fehlt bei einem preisgeführten Artikel die Auswahl, scheitert die gesamte Angebotsübernahme atomar.

## Kalkulation und Leistungsstückliste

`business_pricing.preview` akzeptiert additiv:

- `source_price_selection` neben `source_article_id` und `source_article_revision` als ausdrücklich gewählte Einkaufspreisquelle der Basiskosten;
- `price_selection` je Element in `components` neben Artikel-ID, Revision und Menge.

Beide Auswahlobjekte verwenden denselben Vier-Felder-Vertrag wie oben. Die Preisrolle wird serverseitig als `purchase_net` geprüft. Ein mitgeschickter `base_cost_net` muss dem aus der gewählten Quelle resultierenden bisherigen Basiskostenschritt entsprechen; eine abweichende manuelle Zahl wird mit 409 zurückgewiesen. Ein preisgeführter Quellartikel ohne Auswahl darf seinen technischen Null-/V1-Wert nicht als Kalkulationsquelle verwenden.

Stücklistenkosten werden als `quantity * price_net / price_base_quantity` berechnet und erst am bestehenden Cent-Rundungsschritt gerundet. Rohpreis und Bezugsmenge stehen vollständig in `source_articles`, `components` und dem eingebetteten `catalog_price_snapshot`. Beispiel: `3 * 1 EUR / 3 ST` ergibt `1.00 EUR` Stücklistenkosten. Bei Verwendung als **Basiskosten je kalkulierter Einheit** bleibt der bisherige explizite Cent-Schritt bestehen: `1 EUR / 3 ST` ergibt dort `0.33 EUR`; dieser bestehende Kalkulationsschritt wird nicht mit einer präziseren Beleg-Preisbasis verwechselt.

Die Bestätigung mit `pricing`, `pricing_hash` und `price_confirmation` prüft die Quellen erneut. Eine inzwischen korrigierte Preisrevision wird nicht mehr neu bestätigt. `save_article` übernimmt dieselben datierten Kostenquellen in Leistungsstücklisten; eine nachfolgende reine Namensänderung behält ihre ursprünglichen Fakten, auch wenn der referenzierte Artikel oder Preis inzwischen eine weitere Revision besitzt.

## Historie, Wiederherstellung und Parallelität

Bestehende Belegpositionen dürfen ihre unveränderte Preisquelle weiterführen, ohne deren aktuellen Head zu verlangen. Auch ein früher undatierter Artikelbeleg bleibt erhalten, wenn der Artikel später preisgeführt wird; sein alter Preis darf dadurch keine neue Preisfreigabe werden. Konversion und finale Archive behalten ihre historischen Positionen. Wiederverwendbare Vorlagen dürfen keine datierte Artikelpreisfreigabe mitnehmen; der konkrete Preis ist im neuen Beleg auszuwählen.

Historische Validierung prüft angenommene Originale, Preisrolle, Auswahlstichtag und Artikelbindung. Bei Kalkulationen werden zusätzlich Quellartikelrevision/-hash, ausgewählte Preisreferenz, Mengen und Bezugsmenge gegen den eingefrorenen Nachweis geprüft. Die Wiederherstellungsprüfung erfasst auch frühere Beleg- und Artikelversionen, nicht nur aktuelle Datensätze.

Vor mehrzeiligen Schreibvorgängen werden alle ausdrücklich ausgewählten Preisquellen mit `lock_selections` in stabiler Reihenfolge gesperrt. Einzelauflösungen verwenden weiterhin `resolve_selection(..., lock=True)`. Reine Vorschauen verwenden keine Schreibsperren. Dies umfasst direkte Belegauswahlen, eingebettete Kalkulationen und Leistungsstücklisten; historische Snapshots lösen keine neue Preiswahl aus.

## Nachweise

**19 neue Consumerfälle, 68 Tests insgesamt erfolgreich.** Der kombinierte Lauf umfasst die neuen Consumerfälle sowie die vorhandenen Beleg-, Kalkulations-/Aufmaß- und CRM-Verkaufstests einschließlich vorhandener HTTP-Prüfungen. Protokoll: `docs/evidence/catalog-price-consumers-2026-11-04-tests.txt`.

Geprüft sind insbesondere November-/Dezembergrenzen, Korrektur alter Preise, bytegleiches finales Angebots-PDF nach Korrektur, exakte Bezugsmenge, ausdrücklich belegter Nullpreis, getrennte Steuerentscheidung, falsche Rollen/fehlende Auswahl, gefälschte Positions-ID, entfernte oder neu gehashte falsche Provenienz, alte V1-Belege nach Umstellung, veraltete Kalkulationsvorschau, historisches Stücklistenoriginal und sortierte Vorlocks. Ein tatsächlicher Manipulationsfall an einer früheren Belegversion mit neu berechnetem Dokumenthash wird von der Integritätsprüfung abgewiesen.

`py_compile` und `git diff --check` sind erfolgreich. Keine Commits/Staging. Die PostgreSQL-/Gesamtpaketprüfung und beide V2-Oberflächen bleiben Teil der parallelen Gesamtintegration durch den Domainowner; dieser Teilnachweis behauptet deren Abschluss nicht.
