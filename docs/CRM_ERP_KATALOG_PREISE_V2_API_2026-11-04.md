# Eigener datierter CSV-v2-Vertrag

Stand: 4. November 2026, abgegrenztes Paket im isolierten V2-Baum. Backendkern, direkte Verbraucher sowie Browser und Native sind umgesetzt; die unabhängige Nativeprüfung ist abgeschlossen. Die gemeinsame Integration mit den neueren Root-Bausteinen wird gesondert geprüft. Das ist keine Lieferantenformatabnahme und keine Gesamtziel-Fertigmeldung. V1/DATANORM-Originale und Quittungen werden nicht umgeschrieben.

## Format und Entscheidungen

Eigenes Profil `catalog_csv_v2`, UTF-8 (BOM erlaubt), Semikolon, exakt diese Kopfzeile:

```text
price_id;code;name;unit;price_role;price_net;price_base_quantity;currency;tax_rate;valid_from;valid_until
```

Original 1 Byte bis 2 MiB, maximal 2.000 Preiszeilen. `price_id` ist je Quelle eine dauerhafte Preiskennung; innerhalb einer Datei eindeutig. `code` bezeichnet die Quellartikelnummer, die ausdrücklich an einen vorhandenen aktiven Materialartikel mit gleicher Einheit gebunden oder als neuer Artikel angelegt wird. Mehrere Preisrollen/-zeiträume derselben Quellnummer sind möglich. Keine automatische Zusammenführung verschiedener Quellen. Name/Einheit dürfen innerhalb einer Datei für dieselbe Nummer nicht abweichen. Abweichender Name zum Zielartikel braucht ausdrückliche Bestätigung; Einheiten werden nicht umgerechnet.

Rollen `purchase_net` und `sales_net`, Währung `EUR`. Betrag/Bezugsmenge als nicht negativer Dezimaltext mit bis zu vier Nachkommastellen; Basis strikt positiv. Ein ausdrücklich belegter Nullpreis bleibt möglich. Betrag und Basis bleiben getrennt, also beispielsweise 1 EUR pro 3 ST. `valid_from` ist Pflicht; beide Datumsgrenzen gelten einschließlich. Leeres `valid_until` bedeutet ausdrücklich offen. Ein Uploaddatum ist kein Gültigkeitsdatum. Steuer ist eine Quellenangabe; der Beleg behält seine eigenständige konkrete Steuerentscheidung neben dem unveränderten Originalnachweis.

## Autorisierung und Route

Alle Pfade unter `/business/catalog-prices`. Lesen/Original/Preview/History einer Quelle benötigen `settings.manage` und `finance.read`; Mutationen zusätzlich `finance.write` und aktiviertes Dokumentmodul. Preis-Auswahl `candidates` und Consumerauflösung benötigen `finance.read`, keine Quellenverwaltungsrechte. Aktuelle Rechte werden serverseitig geprüft. Reine POST-Vorschauen sind ohne Schreibmodus lesbar. POST akzeptiert keinen Querykanal; GET keinen Body oder unbekannte Filter. Mutationsaufträge haben `request_id` (32 lowercase Hex), unverändertes Replay liefert die ursprüngliche Quittung. Eine anderweitige Verwendung derselben ID ist 409.

| Methode/Pfad | Eingabe/Ergebnis |
|---|---|
| GET `/sources` | `items`, Profil; unveränderliche Quellen mit `source_version` |
| POST `/sources` | `request_id,name,reference`; keine Anbieter-Verbindung |
| GET `/sources/{id}/imports` | optionale `offset`/`limit` (max.50); Originalmetadata, Status, Zeilenzahl |
| POST `/sources/{id}/imports` | `request_id,catalog_revision,filename,content_base64`; tatsächliches Original, SHA256, geparste Zeilen; gleicher Quellrevisionsname mit anderen Bytes/Dateiname =409 |
| GET `/imports/{id}` | Original, Zeilen, Status, `application`, `current_source_version`, vorhandene `bindings` und `price_heads` |
| GET `/imports/{id}/original` | Tatsächliche Originalbytes, einfacher Originaldateiname |
| POST `/imports/{id}/preview` | siehe unten; ausschließlich lesen |
| POST `/imports/{id}/apply` | vollständige geprüfte Entscheidungen + `request_id,preview_sha256,confirmation:true` |
| GET `/prices/{id}/history` | unveränderliche aktive und zurückgenommene Revisionen einschließlich Hash |
| POST `/prices/{id}/withdraw` | `request_id,revision,sha256,reason,confirmation:true`; neue Rücknahmerevision |
| POST `/candidates` | `article_id,price_role,effective_on`, optional `source_id`; ausschließlich lesen |

`source_version` ist eine monotone Quellenänderungskennung, **kein** linearer Importzähler. Die ursprüngliche Importkennung bleibt erhalten, wenn ein anderer Import den Quellenstand geändert hat. Dasselbe noch nicht angenommene Original kann danach mit ausdrücklich aktualisiertem `expected_source_version` neu geprüft werden.

## Bindung, Vorschau und ausdrückliche Korrektur

```json
{
  "expected_source_version": 0,
  "bindings": {
    "QUELLNUMMER": {
      "action": "create",
      "article_id": null,
      "article_revision": null,
      "expected_binding_revision": 0,
      "confirm_name_difference": false
    }
  },
  "replacements": {}
}
```

Für vorhandene Artikel `action:"bind"`, die tatsächliche `article_id`, aktuelle `article_revision`, und vorhandene Bindungsrevision einsetzen. Detail liefert Vorschläge; eine Artikel-ID darf nicht aus gleicher Nummer erraten werden. Neu anlegen darf ausdrücklich eine alte Bindung ablösen; alte Fakten bleiben unverändert, neue Auswahlen der alten Bindung werden gesperrt.

Preview liefert Original-/Zeilenhash, Entscheidungen, Bindungsunterschiede, vollständige `rows` mit `action:create|correct|unchanged`, `before`, neuer `price`, `preview_sha256`, `ready` und `required_replacements`. Bei erforderlichen Korrekturen ist `ready:false`; die Antwort benennt `external_price_id,revision,sha256` der vorhandenen Revision. Nach sichtbarem Vergleich bestätigt der Bediener die Korrekturen und übermittelt sie als `replacements[external_price_id]={revision,sha256}` in einer **erneuten** Vorschau. Erst `ready:true` mit exakt gebundenem Hash erlaubt Übernahme. Zusätzliche unnötige Korrekturen oder veraltete Hashes sind Fehler. Überlappende aktive Zeiträume derselben Bindung/Rolle sind 409; ein offener alter Preis wird nicht automatisch verkürzt.

Die Application enthält Import-/Quellenkennung, neue Quellenversion, Original-/Previewhash, gebundene Artikel und konkrete Preisrevisionshashes, Auftragskennung/-hash, Ersteller/Zeit. Ein LostACK wird mit exakt dem ursprünglichen Auftrag geprüft, ohne neue ID, Revision oder Originaldatei. Bestehende manuelle Artikelpreise werden durch Import nicht überschrieben. Neu angelegte v2-Artikel haben technische Stammplatzhalter, die durch die nachfolgenden Consumerregeln niemals automatisch verwendet werden dürfen.

## Ausdrückliche Auswahl und Belege

`candidates` liefert je Preis Revision/Hash, Quelle einschließlich ihrer belegten `source_reference` (auch bei gleichen freundlichen Namen), gesamten Preis und Status: `eligible`, `not_yet_valid`, `expired`, `withdrawn`, `retired_binding`, `unit_conflict`. Keine automatische Wahl, auch nicht bei einem einzelnen Treffer. Keine andere Rolle/Quelle, kein älterer Stammpreis als Ersatz. Der Bediener wählt einen fachlichen Tag und eine konkrete geeignete Quelle.

```json
{
  "price_id": "32_hex",
  "price_revision": 1,
  "price_sha256": "64_hex",
  "effective_on": "2026-11-30"
}
```

Der Server bindet daraus `catalog_price_snapshot` mit Vertrag, Quelle/Name, Preisrevision/hash, Auswahlstichtag, unverändertem Betrag/Basis/Einheit/Rolle, Artikelbindung, Originalhash/Import/Zeile und Snapshot-Hash. Historische Snapshots werden gegen ursprüngliche Fakten geprüft, nicht gegen einen späteren aktuellen Preis. Beleg- und Stücklistenpositionen müssen außerdem eine tatsächlich vorhandene ursprüngliche Artikelrevision mit korrektem Hash und damaliger Einheit benennen. Stücklisten halten auch damaligen Namen und Artikelart fest. Bei einer Änderung darf jedes vorhandene historische Stücklistenvorkommen einmal erhalten bleiben; zusätzliche Kopien benötigen eine neue ausdrückliche gültige Auswahl. Zwei ursprünglich ausdrücklich bestätigte gleiche Komponenten bleiben beide erhalten.

- Dokumentposition: `catalog_price_selection` mit `sales_net`, zusätzlich aktuelle `article_id/article_revision`. Betrag/Basis/Einheit strikt quellengebunden; neue Managed-Position ohne Auswahl =409. Gespeicherte unveränderte historische Positionen und Konversionen behalten den ursprünglichen Snapshot.
- Kalkulation: `source_price_selection` für die Basiskostenquelle beziehungsweise `components[].price_selection`, jeweils `purchase_net`. Mitgesendete widersprüchliche Basiskosten =409. Komponenten rechnen Menge × Rohbetrag / Basis vor dem bestehenden Cent-Rundungsschritt.
- Bestellvorschlag: `items[].catalog_price_selection`, `purchase_net`, neben Artikel-ID und Menge. Freigabe prüft die Auswahl erneut. Finanzberechtigte Leser erhalten den gespeicherten Snapshot im Bestell-DTO; andere nur den Hinweis, dass eine datierte Quelle erforderlich ist. Bei der Dokumentation einer extern erteilten Bestellung muss `ordered_on` dem ausdrücklich gewählten Preisstichtag entsprechen und die Preisrevision weiterhin aktuell sein. Eine bereits dokumentierte Bestellung bleibt nach Preiskorrektur unverändert. Gespeicherte V2-Bestellartikel werden vollständig gegen die benannte ursprüngliche Artikelrevision geprüft; Restore prüft dies auch für noch nicht extern dokumentierte Vorschläge. Heutige Artikeländerungen ersetzen diese Originalfassung nicht.
- Sales-Angebotsübernahme: dieselbe Dokumentauswahl pro gewählter Artikelposition; Artikelreferenz bleibt erhalten.
- Wareneingang: Für v2-geführte Artikel ist ein tatsächlicher `unit_cost_net` Pflicht; weder Angebots-/Katalogpreis noch technischer Stammwert ersetzen ihn. Expliziter tatsächlicher Nullpreis ist erlaubt. Entnahmen/Rückgaben bleiben am historischen Lagerjournal gebunden.

Mehrere Quellen werden im Schreibvorgang in sortierter Reihenfolge gesperrt; parallele Übernahmen prüfen danach den aktuellen Quellenstand. Original-/Binding-/Preis-/Acceptance-/Requesttabellen sind unveränderlich. Datenbank-Backup/Restore behält alle Quittungen; der portable Unternehmens-ZIP enthält Fachfakten/Originalbytes, weiterhin keine technischen Replayquittungen.

## Nachweise und verbleibender Umfang

Backend-Einzelbelege: 45 gezielte Domain-/Consumer-/Einkaufs-/Integritäts-/SQLite-Restore-Fälle, drei echte lokale HTTP-Fälle und drei tatsächliche PostgreSQL-Fälle (MFA/HTTP/2MiB, getrennte Runtimeverbindungen, Dump/Restore mit Novemberangebot). Der unabhängige Review ergänzt zwölf unveränderte Gegenfälle; drei davon waren vor den gezielten Korrekturen rot. Die zuvor abgeschlossene breite Backendregression umfasste 1.608 Tests mit einem Plattform-Skip; die eng danach ergänzten historischen Identitätsprüfungen sind inzwischen zusätzlich unabhängig nachgeprüft. Die PostgreSQL-Fälle lagen vor diesem letzten Identitätsnachtrag; dessen integrierte PostgreSQL-Nachprüfung führt Root aus. Der spätere integrierte Rootlauf bleibt gesondert erforderlich.

Der Browser besitzt echte Dateiauswahl, Originaldownload, sichtbare Differenz mit gesonderter Korrekturbestätigung, History und ausdrückliche datierte Preiswahl. Ein tatsächlicher Chromium-/MFA-/HTTP-Lauf prüft November-/Dezembergrenze, 390-Pixel-Ansicht, verlorene Upload-/Annahmeantworten, unverändertes altes Angebot nach Korrektur sowie Bestellfreigabe und ausdrücklich datiertes externes Bestelldokument. Zusätzlich prüfen 32 gezielte Nodefälle Original-/Quittungsbindung, spät eintreffende private Antworten, Rechte-/Kontextwechsel und exakten Replay. Eine unklar beantwortete datierte Dokument-/Bestellübernahme behält ihre Originaldaten und Auftragskennung auch bei 403/404/unklarem 409; eine Wiederholung prüft frische Fähigkeiten für das ursprüngliche Projekt. Undatierte Altaufträge behalten ihren bisherigen Vertrag.

Native: 70 neue Fälle, kombinierter Bestand 182/182 grün, Analyse von 14 betroffene Dateien ohne Befund. Echte HTTP-Strecke umfasst 2 MiB/2.000 Preiszeilen, Originalbytes, Vorschau/Übernahme und Dokument-LostACK. Der Bericht [CRM_ERP_KATALOG_PREISE_V2_NATIVE_2026-11-04.md](CRM_ERP_KATALOG_PREISE_V2_NATIVE_2026-11-04.md) und das [native Hashhandoff](evidence/catalog-prices-native-2026-11-04-handoff.json) halten den genauen Umfang fest; der [unabhängige Nativeabschluss](evidence/catalog-native-independent-2026-11-04/README.md) besteht 87/87 Fälle (17 neue Gegenfälle plus 70 gezielte Ownerfälle) einschließlich tatsächlichem HTTP. Die neue Reviewdatei hat 0 Analysebefunde; geprüfte Runtime und Ownerfixtures entsprechen bytegenau dem Handoff. Der Bestellidentitätsnachtrag ist unabhängig mit 17/17 Fällen bestätigt. Browser-Gesamtregression 554/554 und tatsächliche alte Rechnungskette sind nach dem eng datierten Dialogkontextfix grün. Unabhängige Lieferantenspezifikationen, Staffel-/Rabattmodelle und Fremdwährungen sind nicht Teil dieses eigenen CSV-Vertrags.
