# Belegte Jahreswerte vor Softwarebeginn – API v1

Stand 04.11.2026; isolierter Kandidat, noch keine Browser-/Nativeoberfläche.
Backendfamilie `business_accounting_year_openings`, reine Regeln
`accounting_year_opening_rules`, EÜR-Anschluss `accounting_year_opening_sources`.
Regelversion `de_euer_same_year_carryover_v1`, DTO-Version 1.

## Tatsächliche Fixture

`docs/fixtures/accounting_year_values_v1.json` wurde über tatsächlich angenommene
synthetische Domänenvorgänge erzeugt, einschließlich Originalupload, Preview,
Confirm, EÜR-Übernahme, tatsächlicher Folgezahlung, Export und Korrektur.
Generator: `scripts/generate-accounting-year-values-fixture.py`.

- `complete`: ursprünglicher Lieferantenbeleg 119,00, im August tatsächlich59,50
  bezahlt; im November weitere59,50. Jahresausgabe119,00, historischer
  VAT-input19,00 im Juni, neue November-Vorsteuer0. Neue Geldbewegung59,50;
  Anfangssaldo1000,00 bleibt unverändert und berechneter Kontostand940,50.
- `partial_then_corrected`: zunächst August–Oktober mit vollständiger Deckung nur
  dieses Teilzeitraums, weiterhin unvollständiger Jahresbericht. Explizite
  EÜR-Gegenbuchung, unverändertes Void und vollständige neue Jahresfassung;
  alter Export unverändert.
- `closed_trade`: zusätzliche vollständig erledigte externe Rechnung mit eigenen
  Originalen, ursprünglichen Zahlungs-/Steueridentitäten und Kontrollsummen.
  Sie erzeugt keinen offenen Posten und keine Geldbewegung.

Previews werden unmittelbar beim tatsächlichen Aufruf aufgezeichnet, nicht aus
Confirmantworten nachgebildet. Jeder Fall enthält Anfangs-/Endzustand, Quellen,
Originalmetadaten/Bytes, Historie, Berichte und echte EÜR-Vorschauen. UUIDs und
Annahmezeitstempel werden bei erneutem Erzeugen neu erstellt. Die eingecheckte
Fixture und ihr SHA-256 werden im Abnahmenachweis gebunden.

## Geschützte Routen

Basis `/business/accounting/year-values` (OfficeApi verwendet den üblichen
Business-Präfix). Exakte Methoden und JSON-Felder, keine Zusatzfelder.

| Methode | Pfad | Bedeutung |
| --- | --- | --- |
| GET | Basis | Revisionsstand, aktuelles Profil, Originale und letzte Jahresfassungen |
| GET | `/history?entity_key=2026` | Alle ursprünglichen Fassungen des Jahres |
| GET | `/years/2026?revision=1` | Genau die immutable EÜR-Quellenprojektion |
| GET | `/originals/{id}` | Geschützte Originalbytes, `no-store` |
| POST | `/originals` | Original an das vierstellige Jahr binden |
| POST | `/preview` | Frische Profil-/Original-/Bestandsprüfung und Vorschau |
| POST | `/confirm` | Atomare immutable Annahme der exakten Vorschau |

Jahreskennung ist ausschließlich `20xx`, identisch mit dem Jahr des bestätigten
Softwarebeginns. Ein aktiver Vorgang pro Jahr; Revisionen ersetzen niemals
historische Originale. Ein neuer UI-Vorgang benötigt eine neue `request_id`;
bei Antwortverlust wird derselbe unveränderte Befehl wiederholt.

Lesen: aktuelle `accounting.read` und `finance.read`. Schreiben zusätzlich
`accounting.admin`, `accounting.prepare`, `finance.write`, aktive Finanzfunktion,
aktuelle Modul-/Runtimefreigabe und bestätigter Restore. Offlineannahmen sind
nicht freigegeben. Neue Quellannahmen benötigen aktuelles Buchführungsprofil;
exakte alte Annahmen prüfen heutige Rechte/Gates und erhalten alte Quittungen.

## Upload und Jahresannahme

Uploadfelder: `request_id`, `entity_key`, `filename`, `media_type`,
`content_base64`. Unterstützt PDF/PNG/JPEG, höchstens5MiB. Antwort enthält
Original-ID, SHA-256, Größe, ursprünglichen Uploader/Annahmezeit und geschützten
Pfad. Gleiche Bytes/Jahresbindung behalten ihre ursprüngliche Identität.

Previewfelder:

```
expected_revision, state_hash, entity_key, profile_ref,
operation: "year_values", payload, reason
```

`profile_ref`: `{id,revision,entry_sha256}`. Confirm ergänzt `request_id`,
`preview_hash`, `confirmation:true`. Abgewiesene veraltete Confirmanfragen
tragen `request_resolution:"not_accepted"`; eine tatsächlich angenommene
identische Anfrage liefert dagegen ihre ursprüngliche Fassung.

`payload` besitzt genau:

```
status: "active" | "void"
coverage: {from:"2026-01-01", through:"2026-10-31"}
sources: [...]
controls: [{ledger,category,account,amount}, ...]
ledger_proof: {original_id,sha256}
attestations: {
  continuous_method:true,
  original_journal_complete:true,
  no_unsupported_values:true
}
```

Das eigenständige `ledger_proof` belegt den erklärten Zeitraum, alte Journal-
identitäten und Kontrollsummen. Es darf nicht dieselben Bytes wie ein einzelner
Rechnungs-/Zahlungsbeleg besitzen. Ein explizit belegtes Nulljournal wird nur
angenommen, wenn bekannte Quellen diesem Nullbestand nicht widersprechen.
Ein fehlender oder nicht belegter Altbestand wird niemals als Null vorbelegt.

`coverage` ist ein zusammenhängender Zeitraum desselben Jahres vor Beginn. Die
Lücke vor dem Softwarebeginn entfällt im Jahresbericht nur bei tatsächlicher
vollständiger Deckung bis zum Vortag. Unterschiedliche Teilzeiträume werden
nicht automatisch vereinigt; unvollständige Jahre behalten
`partial_period_profile_coverage` und kein abschließendes `euer_surplus`.

## Zwei ursprüngliche Quellenarten

Gemeinsame Quellenfelder:

```
accounts: {net:"5400",tax:"1406",input_vat:"1406"}
cash_entry_keys: ["originale Buchungsidentität je alter Zahlung"]
vat_entry_key: "originale Vorsteuerbuchungsidentität" | null
```

Konten sind ausdrücklich geprüfte vierstellige SKR04-Konten. Die Controls
enthalten exakte vorzeichenbehaftete Centwerte, getrennt nach Journal/Kategorie/
Konto, keine automatisch unterstellte Summe. Leer ist nur bei belegtem Nullwert
zulässig. Die ursprüngliche Journalsystem-/Buchungsidentität und wirtschaftliche
Rechnungsidentität dürfen nicht doppelt übernommen werden.

1. `kind:"opening_item"` mit `entry_id`, `entry_hash`: liest ausschließlich die
   wirkliche unveränderte bestätigte Altpostenfassung. Beträge, Tage, Originale,
   externe Identität und ausgeübte alte Vorsteuer werden nicht frei wiederholt.
2. `kind:"closed_trade"` mit `record`: dieselben strikten Rechnungs-/Altzahlungs-
   und alten Vorsteuerfelder wie im [Altpostenvertrag](CRM_ERP_ALTPOSTEN_API.md),
   jedoch nachweislich vollständig vor Beginn bezahlt. Alle Proofs verweisen
   auf geschützte Jahresoriginale. Ein vorhandener Altposten oder lokaler Beleg
   muss seinen kanonischen Weg benutzen; eine Kopie ist nicht zulässig.

Die enge Fassung unterstützt fortgeführte EÜR, Regel-/Istbesteuerung, vollständig
betriebliche gewöhnliche inländische19-/7-Prozent-Fälle mit einer belegten
Gesamt-Netto-Steuergruppe. Ein Rechnungscan mit neuer externer Kennung darf die
ursprüngliche Gegenpartei-/Rechnungsnummer-/Datumsidentität nicht duplizieren.
Unpassende ursprüngliche Centaufteilungen werden abgewiesen, nicht neu verteilt.

Alte ausgeübte Vorsteuer wird mit ursprünglichem Anspruchstag, deklariertem
Zeitraum und tatsächlichem `deducted_on` erhalten. Sie ist eine historische
Journalprojektion, kein neuer `input_vat`-Vorgang. Alte Lieferantenzahlungen
behalten unabhängig davon ihre tatsächlichen EÜR-Zahlungstage. VAT im Vorjahr
und Zahlung im laufenden Jahr erzeugt nur den laufenden EÜR-Anteil. Zahlungen an
das Finanzamt werden niemals aus einer Rechnung abgeleitet. Anlagen, Lohn,
Privatanteile, Methodenwechsel und andere Sonderfälle sind in diesem Umfang
nicht freigegeben; bekannte AfA vor Beginn verhindert eine unzutreffende Deckung.

## EÜR, Korrekturen und Sicherung

Die Quelle erzeugt keine aktuelle Geldbewegung oder neue steuerliche Forderung.
Der ausdrückliche EÜR-Vorgang lautet:

```
operation: "opening_year_values"
payload: {year:"2026", revision:1, source_hash:"..."}
```

Er kopiert nur die verifizierten historischen Zeilen mit ihren tatsächlichen
alten Tagen. Der normale `cash`-/`input_vat`-Datumsschutz bleibt unverändert.
`historical_year_values` kennzeichnet im Bericht den gebundenen alten Zeitraum
und die Quelle; ohne eine solche Quelle bleibt die alte Berichtsgestalt erhalten.
Neue Quellenprobleme werden als explizite `opening_year_values_*`-Issues gemeldet.

Vor einer Quellenkorrektur muss die aktive EÜR-Übernahme ausdrücklich
gegengebucht werden. Betroffene geschlossene Perioden werden vorher geöffnet.
Ein Void übernimmt die alte Fassung unverändert außer `status`; eine korrigierte
neue Fassung erhält neue Revision und Quittung. Abhängige kanonische Altposten
können ihre alten Beträge nicht hinter einer bereits aktiven Jahresübernahme
ändern. Gespeicherte alte Berichte und Exporte werden nicht neu berechnet.

Neue Tabellen: `business_accounting_year_opening_originals`, `_events`, `_requests`.
Finanzhorizont15/Restorebericht16 ergänzt die älteren Versionen. Datenbankruntime
besitzt nur SELECT/INSERT, keine UPDATE/DELETE/TRUNCATE-Rechte. Originalbytes,
Events und Annahmequittungen werden im tatsächlichen Restore reproduziert;
ältere bereits akzeptierte Freigabequittungen bleiben identisch überprüfbar.
