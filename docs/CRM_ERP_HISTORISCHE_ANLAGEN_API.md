# Historische lineare Anlagen: laufende Umsetzung und API-Vertrag

Stand 04.11.2026. Arbeitsbaum `/workspace/smartplan-historical-assets-20261104`.
Der Baselinevergleich hat alle 1563 Dateien des Manifests
`work/verification/historical-assets-opening-backend-baseline.json` bestätigt.
Der später separat geprüfte Geldkonto-Summenfix ist unter
`work/verification/historical-assets-opening-large-balances-followup.json`
mit Vor-/Nachhash dokumentiert. Keine Produktivdaten, keine Übermittlung.

## Fachlich begrenzter Vertrag

Regel `de_historical_linear_assets_v1`, Feature `accounting_historical_assets`,
Capability/Modul `business_accounting_asset_openings`. Ausgangspunkt und aktuell
gelesene amtliche §§ 4 Abs. 3, 7 und 9b EStG stehen im
[Vertragsentwurf](CRM_ERP_ALTE_ANLAGEN_VERTRAGSENTWURF_2026-11-04.md).

Unterstützt sind vollständig betrieblich genutzte bewegliche Anlagen mit
belegter unveränderter linearer AfA. Anschaffung und ursprünglicher AfA-/Nutzungs-
beginn müssen in derselben Kalendermonatsperiode und vor dem bestätigten
Buchführungsbeginn liegen. Ein fachlich abweichender Beginn, Privatanteile,
Gebäude, Methodenwechsel, Sonder-AfA, degressive AfA, GWG, Sammelposten und
Abgänge sind damit nicht automatisch bewertet. Unvollständige oder unpassende
Vortragsdaten erhalten keine aktive angenommene Anlagenfassung.

Der Belegstand gilt unmittelbar vor `profile.bookkeeping_start`, 00:00
Europe/Berlin. Die Software setzt weder Anschaffungsdatum noch Nutzungsdauer
neu. Die Übernahme erzeugt keinen neuen Aufwand, keine Zahlung, keine Einlage
und keinen erneuten Vorsteuerabzug. Eine ausdrücklich bestätigte Folge-AfA
erzeugt einen EÜR-Aufwand ohne Geldbewegung.

Originale sind PDF/PNG/JPEG bis 5 MiB, an die betriebliche Inventarkennung gebunden.
Eine Inventarkennung wird aus der Inventarnummer mittels Unicode-NFKC,
Rand-Leerzeichenentfernung und vollständigem Unicode-Casefold gebildet.
Originalnummer und normalisierte Kennung sind jeweils auf 100 Unicodezeichen
begrenzt; eine längere Casefold-Erweiterung wird ausdrücklich abgewiesen. Eine Anlagenliste kann
mehrere Anlagen belegen; dieselbe Kombination aus Original-SHA256 und
normalisierter Position darf jedoch nicht unter mehreren Kennungen aktiv
übernommen werden. Ein bereits als gewöhnliche EÜR-Anlage gebundener
Originalhash darf nicht gleichzeitig als historische Anlage angesetzt werden.

## Originalwerte und Rundung

Alle eingegebenen Beträge sind kanonische nichtnegative EUR-Centtexte, bei
Bruttokosten/Basis positiv. Die Basis entspricht Bruttokosten minus abziehbarer
Vorsteuer; die vorliegende Version umfasst ausschließlich den vollständig
betrieblichen Anteil. Vorjahres-AfA, bereits im Startjahr gebuchte AfA und
Eröffnungsbuchwert müssen zusammen exakt diese Basis ergeben.

Das tatsächlich dokumentierte Altverfahren ist ausdrücklich auszuwählen:

| `rounding` | Bedeutung |
| --- | --- |
| `cumulative_months_half_up` | Differenz der kumulierten, auf Cent gerundeten ursprünglichen Monatsanteile an den Jahresgrenzen |
| `annual_half_up` | Ursprünglicher Jahres-/Teiljahresanteil auf Cent gerundet |
| `monthly_half_up` | Ursprünglicher Monatsanteil auf Cent gerundet und über die tatsächlichen Jahresmonate summiert |

Alle drei bewahren höchstens die ursprüngliche Basis; der letzte Jahresbetrag
enthält die dokumentierte verbleibende Centdifferenz. Es sind technische,
ausdrücklich belegte Alt-Rundungsverfahren, keine drei steuerlichen Wahlrechte.
Die belegte Vorjahres-AfA muss zu diesem vollständigen ursprünglichen Plan
passen. Eine Abweichung wird nicht rückwirkend überschrieben oder automatisch
als laufende Nachholung gebucht. Ein anderer Altfall bleibt zu klären.

Die bereits im Startjahr gebuchte AfA ist ein eigener Pflichtwert mit
Originalbindung. Am 1.1. ist sie 0, sonst höchstens die ursprüngliche Jahresquote.
Die nach Übernahme verfügbare Jahres-AfA ist diese Quote abzüglich des bereits
gebuchten Betrags. Beispiel: Basis 3600, ursprünglicher Beginn Januar 2024,
36 Monate, Buchführungsbeginn 17.07.2026, Vorjahres-AfA 2400, bereits 2026 gebucht 500,
Restbuchwert 700: Die Folge-AfA 2026 beträgt 700. Keine Neuberechnung 1200 oder
Restbuchwert/Restlaufzeit. Eine vollständig abgeschriebene weiterhin genutzte
Anlage bleibt im Verzeichnis mit ausdrücklich belegtem Nullbuchwert.

## API

Basis `/business/accounting/historical-assets`; native relative Pfade beginnen
bei `/accounting`. Lesen erfordert bestehendes `accounting.read` und
`finance.read`; Schreiben zusätzlich `accounting.admin`, `accounting.prepare`
und `finance.write` sowie aktuelle Modul-, Runtime- und Restorefreigabe.
Bankrechte werden für diese Anlagenquellen nicht zusätzlich verlangt.

| Route | Vertrag |
| --- | --- |
| GET Basis | Globalrevision/Hash, aktuelles Profil/ref, angenommene aktuelle `items`, `originals`, `can_prepare`, Originalgrenze und unterstützte Rundungsverfahren |
| POST `/identity` | Exakt `{inventory_number}` → `{schema_version:1,inventory_number,asset_key}`; serverseitige Unicode-Zuordnung ohne Datenänderung oder Vorgangskennung. Leserechte, jedoch reguläre zentrale Online-/Modulfreigabe für POST |
| POST `/originals` | Exakt `request_id,asset_key,filename,media_type,content_base64`; Originalmetadaten mit ID, Hash und Downloadpfad |
| GET `/originals/ID` | Unveränderte Originalbytes; Rechte werden frisch geprüft |
| GET `/history?asset_key=...` | Alle unveränderlichen Fassungen dieser normalisierten Inventaridentität |
| POST `/preview` | Exakt die nachstehenden Eingaben, keine Schreibwirkung |
| POST `/confirm` | Vorschauauftrag ergänzt um `request_id,preview_hash,confirmation:true`; angenommene unveränderliche Fassung |

Vorschau:

```text
expected_revision, state_hash
asset_key: normalisierte Inventarkennung
profile_ref: {id,revision,entry_sha256}
status: active | void
opening_date: exakt profile.bookkeeping_start
asset: {
  inventory_number,description,
  asset_kind: movable, business_use: exclusive_business, method: linear,
  rounding: eines der drei ausdrücklich belegten Altverfahren,
  acquired_on,use_start,life_months,
  acquisition_gross,deductible_input_tax,cost_basis,
  depreciation_before_start_year,depreciation_in_start_year,opening_book_value,
  account: geprüfte vierstellige SKR04-Anlagenzuordnung,
  unchanged_linear_history_confirmed:true
}
source: {original_id,sha256,position,history_through}
reason
```

`history_through` ist exakt der Vortag des Buchführungsbeginns. Die angenommene
Fassung bindet vollständiges Profil, Originalmetadaten/Hash/Position,
ursprünglichen Jahresplan, verbleibende Startjahres-AfA, Vorgänger und Quittung.
Die globale Sequenz und Folge je Inventarkennung bleiben unveränderlich.
Korrektur erhält eine neue Fassung; Aufhebung übernimmt Anlage, Quelle, Datum
und Profil der aktiven alten Fassung unverändert. Eine neue Request-ID ersetzt
keine unklare alte Antwort. Bei identischer angenommener Wiederholung gelten
frische Rechte und Gates, aber keine Umdeutung auf die heutige Profilfassung.

## EÜR-Folge und Schutz bestehender Stände

Der neue wirtschaftliche Vorgang `opening_depreciation` verwendet das vorhandene
EÜR-Vorschau-/Annahmeverfahren. Sein Payload ist exakt:

```text
asset_entry_id, source_hash, year, account
```

Die Quelle wird aus der tatsächlichen angenommenen Anlagenfassung gelesen.
Sie besitzt `kind:opening_asset`, eigene Regelversion, Originalreferenzen und
Hash. Bereits erforderliche frühere positive Folgejahre müssen gebucht sein.
Jahresquoten 0 brauchen keine Scheinbuchung. Eine spätere aktive Folge-AfA muss
vor der Gegenbuchung einer früheren rückwärts aufgelöst werden. Aktive AfA
sperrt eine Änderung ihrer Anlagenquelle; geschlossene betroffene Perioden
erfordern die vorhandene begründete Wiederöffnung.

Live-EÜR-Ausgaben zeigen `historical_assets` und offene Prüf-/AfA-Fälle;
`cash_movements` erhält aus der Anlagenübernahme nichts. Unzugeordnete
Anlagenoriginale erscheinen als `historical_asset_review_missing`. Gespeicherte
frühere Exporte behalten ihre Originalberichte und CSV-/Quellenhashes. Neue
Anlagenzeilen werden bei Integritätsprüfung gegen die unveränderliche Quelle
und den damaligen Journalpräfix geprüft. Ein Report mit gebuchter historischer
AfA darf das Anlagenfeld nicht durch Weglassen als alten Bericht ausgeben.
Die neue Live-Navigation heißt `historical_assets_path`.

Drei neue unveränderliche Tabellen tragen das Paket:
`business_accounting_asset_opening_originals`, `_events`, `_requests`.
Der kombinierte Finanzhorizont wird 13, die aktuelle Restore-Abnahme 14.
Alte Berichte werden weiterhin unter ihrer exakten alten Feld-/Tabellenmenge
validiert. Der Unternehmensdatenkatalog führt genaue Spalten und Finanzrechte;
technische Annahmequittungen bleiben aus dem portablen Fachauszug ausgeschlossen.

## Tatsächlicher Fortschritt und Nachweise

Backend, Originaltransport, Rechte, Migration, Export, PostgreSQL und Browser
sind mit synthetischen Daten geprüft. Die unabhängigen Gegenproben enthalten
900 rationale Cent-/Kalenderkonstellationen und einen tatsächlich mit altem
EÜR-Code erzeugten Export. Browser und native Oberfläche verwenden dieselbe
vom Backend erzeugte Fixture; keine erfundenen DTOs oder Unternehmenswerte.

- [Fortschritt, Prüfungen und Integration](CRM_ERP_HISTORISCHE_ANLAGEN_FORTSCHRITT_2026-11-04.md)
- [Unabhängiger Rechenkern-/Domainreview](evidence/historical-assets-independent-2026-11-04/README.md)
- [Echte Fixture](fixtures/accounting_historical_assets_2026.json), regenerierbar
  mit `scripts/generate-accounting-historical-assets-fixture.py`.

Die native Abnahme und unabhängige Browsergegenprüfung laufen noch. Das
Gesamtziel des CRM/ERP bleibt offen; dieses Paket bestätigt weder echte
Unternehmenswerte noch eine behördliche Steuererklärung.
