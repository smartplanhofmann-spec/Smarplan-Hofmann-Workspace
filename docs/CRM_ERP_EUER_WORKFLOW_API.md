# Eigene EÜR: zusammenhängender Buchführungsablauf

Implementierter und gezielt geprüfter Stand vom 03.11.2026. Der
[Prüfbericht](CRM_ERP_EUER_WORKFLOW_PRUEFUNG.md) beschreibt die tatsächlich
ausgeführten Domain-/PostgreSQL-/Migrations-/Restoreprüfungen und ihre Grenzen.
Keine Übermittlung an DATEV, ELSTER, Banken oder andere Dritte. Amtliche
Grundlagen stehen in [Regelquellen 2026](CRM_ERP_EUER_REGELQUELLEN_2026.md).

## Modell und Zuständigkeit

Additives Modul `business_accounting_euer`, Feature `accounting_euer`, Klasse
`EuerAccounting`. Bestehende Geldfluss-, C1/C2/R1/R2- und Profiljournale bleiben
unverändert. Ein neues globales, unveränderliches Journal bindet Quellen,
geprüfte Einordnungen, Gegenbuchungen, Perioden und Ausgaben zusammen.
`accounting.read` und `finance.read` gelten für das gesamte Unternehmensjournal;
Schreiben braucht zusätzlich `accounting.prepare`, `accounting.admin` und
`finance.write` sowie frische Rechte an sämtlichen verwendeten Originalen.
Produktive Schreibvorgänge nutzen die bestehende PostgreSQL-/Restorefreigabe.
Die gemeinsame Geldbewegungssicht umfasst bestehende CashEvents und ausdrücklich
bestätigte Sonderbewegungen. Alte Vorjournalansichten kennzeichnen ihre engere
Quellabdeckung und verlinken auf `/accounting/euer/sources`. Konten werden aus
denselben versionierten Geldkonten gelesen; ohne belegten Anfangsbestand liefert
die Software Bewegungsnettos und ausdrücklich keinen erfundenen Kontostand.

Keine Instanz bekommt erfundene Gültigkeitsdaten. Das bestehende Profil muss
Einzelunternehmen, EÜR, Regelbesteuerung, Ist-Versteuerung und ausdrücklich
erfasste Gültigkeit/Buchführungsbeginn enthalten. Jeder Eintrag bindet seine
damals geprüfte Profilversion. Konten sind ausdrücklich bestätigte vierstellige
SKR04-Zuordnungen des Bedieners; die Software erfindet keine Kontonummern.

## API

Basis `/api/v1/business/accounting/euer`:

| Route | Ergebnis |
| --- | --- |
| GET Basis | Revision, state_hash, Profilstatus, Kategorien, Perioden, Schreibstatus |
| GET /sources | Berechtigte CashEvents mit genauen dokumentarischen Einheiten sowie Eingangsoriginale, Quellenhashes, aktuelle Einordnung und offene Gründe |
| GET /journal?limit=50&offset=0 | Unveränderliche Einträge, neueste zuerst |
| GET /report?year=2026 | Jahresauswertung, bestätigte Summen und ausdrücklich offene Quellen |
| GET /exports/{id} | Unverändertes eigenes JSON-/CSV-Prüfpaket mit Manifest |
| POST /preview | Unverbindliche Vorschau, ohne Speicherung |
| POST /confirm | Unveränderlicher Journaleintrag und Wiederholungsquittung, 201 |

Vorschaukommando genau `{operation,expected_revision,state_hash,payload,reason,
evidence_reference}`. Bestätigung ergänzt `request_id,preview_hash,confirmation:true`.
IDs sind 32 Kleinhexzeichen, Hashes 64 Kleinhexzeichen, EUR-Beträge kanonische
Centstrings. Der gesamte ursprüngliche Bestätigungsbody bleibt bei unklarer
Antwort wiederholbar. Rechte und Quellen werden auch vor Replay frisch geprüft.
Nur ein nach fehlender Quittung sicher nicht angenommener Konflikt trägt
`request_resolution:'not_accepted'`.

## Vorgänge und fachliche Grenzen

* `cash`: kompletter bestehender CashEvent mit exakten C1/C2/R1/R2-Einheiten.
  Payload: `event_id,source_hash,euer_date,year_rule,lines`. Jede Zeile enthält
  `unit_id,category,business_net,deductible_net,business_tax,deductible_input_tax,
  deductible_tax_cost,account,vat_account`. Kein Bruttobetrag wird neu geteilt.
  Erlösnetto und vereinnahmte USt zählen getrennt als EÜR-Einnahmen;
  abzugsfähiger Aufwand und bezahlte abziehbare Vorsteuer als Ausgaben.
  Privat- und nicht abziehbare Anteile bleiben gesondert sichtbar.
  Bei vollständiger Zahlung muss die Summe bezahlter abziehbarer Vorsteuer die
  ausdrücklich geprüfte Berechtigung des Originals genau erreichen. Eine
  registrierte Anlage kann nicht zugleich als laufender Nettoaufwand abgezogen
  werden. Die bestehenden C1/C2-Quellen unterstützen normale Ausgangsrechnungen;
  Abschlags-, kumulative und Schlussrechnungen bleiben dort offene Fälle.
* `input_vat`: eigener geprüfter Originalbeleg, unabhängig vom Zahlungsdatum.
  Payload: `receipt_id,source_hash,invoice_received_date,service_date,prepayment,
  payment_event_id,entitlement_date,deductible_tax,account,conditions_confirmed`.
  Reguläre Vorsteuer setzt ausdrücklich bestätigte Voraussetzungen, Rechnung
  und Leistung voraus. Vollständige Vorauszahlung benötigt belegte Zahlung;
  Teilanzahlung/Vorauszahlungs-Sonderfälle bleiben offen.
* `external_cash`: ausdrücklich bestätigte Geldbewegung mit geprüftem Original,
  bestehendem Geldkonto und eindeutiger Nachweis-ID. Payload:
  `receipt_id,source_hash,account_id,account_revision,evidence_key,cash_date,amount,
  direction,category,euer_date,year_rule,account`. Umfang: USt-Zahlung/-Erstattung,
  Einlage/Entnahme, Darlehensaufnahme/-tilgung. Kein Bankimport und keine Zahlung
  wird ausgelöst. Gegen vorhandene Cash-Bindungen wird auf Doppelzählung geprüft.
  Originale sind hier Zahlungsnachweise, keine behaupteten Lieferantenrechnungen.
  Original-SHA und Kontonachweis werden quellenübergreifend geprüft, einschließlich
  NFKC-/Leerzeichen-/Großkleinschreibungsnormalisierung. Ein Original repräsentiert
  genau einen vollständig geprüften Sondergeldfluss, keinen mehrzeiligen Bankimport.
  Das Vorjournal kennzeichnet diese Originale auch nach Gegenbuchung als
  `source_role:'payment_evidence'`, `payable:false` und
  `blocked_reason:'external_cash_evidence'`. `paid_amount` und `remaining_amount`
  sind dabei ausdrücklich `null`: Es entsteht keine Lieferantenverbindlichkeit.
* `asset`: neues betriebliches Anlagegut, belegte Basis und ausdrücklich gewählte
  lineare Nutzungsdauer. Payload: `receipt_id,source_hash,description,
  business_basis,use_start,life_months,account`. Keine geschätzten Eröffnungswerte,
  Sonder-/degressive AfA, Anlageveräußerung oder pauschale GWG-Automatik.
* `depreciation`: `asset_entry_id,year,account`; berechnet lineare Jahres-AfA mit
  Anschaffungsmonat, Centrest und bisherigem Buchwert, ohne zweite Cash-Ausgabe.
* `reverse`: `entry_id`; genaue Gegenbuchung des aktiven Eintrags.
* `correct`: `entry_id,operation,payload`; Gegenbuchung und geprüfte Ersetzung
  derselben Quelle in einem atomaren Eintrag. Historische Quellen bleiben lesbar.
  Der wirtschaftliche Quellentyp bleibt dabei erhalten; ein Vorjournal-/EÜR-
  Quellenwechsel ist keine versteckte Korrekturoperation. Abhängige Ausgaben bzw.
  Abschreibungen müssen vor einer Vorsteuer-/Anlagenkorrektur zurückgenommen
  werden. Bei neuer Belegprüfung mit unveränderten Geldbeträgen können Auszahlung
  und ursprüngliche dokumentarische Cents unverändert wiederverwendet werden.
* `period`: `period` als YYYY-MM, `action` close/reopen, `expected_period_revision`,
  `attestation:{bank_reconciled,originals_complete,special_cases_reviewed}`.
  Schließen setzt die ausdrücklichen Prüfaussagen und keine offenen Quellen
  voraus. Wiederöffnen erfordert Grund; gesperrte EÜR-/USt-Perioden verhindern
  Einordnung, Gegenbuchung und rückwirkende Änderung.
* `export`: `year`; speichert eigenes Prüfpaket mit eingefrorenen Summen,
  Journalhorizont, offenen Fällen, Quellenmanifest, CSV und Prüfsummen.

`year_rule` ist entweder `{kind:'cash'}` bei unverändertem Zahlungsdatum oder
`{kind:'ten_day',economic_year,due_date,recurring:true}` bei ausdrücklich geprüfter
Zuordnung zum anderen Jahr. Zahlung und Fälligkeit müssen jeweils im gesetzlichen
Zehntagesfenster liegen; die USt-Periode wird hierdurch nicht verschoben.

Auswertungen sind eigene nachvollziehbare EÜR-/USt-Arbeitsergebnisse und
Beraterprüfpakete. Eine vollständige amtliche Erklärung oder ein geprüftes
DATEV-Importformat wird nicht behauptet. Noch unverbuchte Quellen, unsupported
Sachverhalte, fehlende Vorsteuerentscheidung oder Wiederherstellungsabgleich
bleiben ausdrücklich offen; fehlende Werte werden nicht als Null ergänzt.

## Antwortformen und Ergebnisgrenze

`state` enthält `revision,state_hash,profile,profile_ready,writes_allowed,
rule_version,account_frame,categories,periods,limitations,official_tax_return`.
`sources` enthält `items,issues,cash_movements,account_movements,cash_scope` und
`opening_balances_available:false`. Eine dokumentarische Cash-Einheit führt
`unit_id,version,entry_id,group_id,index,net,tax,gross,rate,tax_category`.
Die Quellenliste enthält daneben ungeprüfte Originale und nicht übernommene
Kundenzahlungen mit expliziten Klärungsgründen.

Eine Vorschau enthält das ursprüngliche Kommando, `profile,rule_version,target,
effect,reverses,postings,artifact,control,preview_hash`. Der gespeicherte Entry
ersetzt `expected_revision,state_hash` durch `sequence,previous_hash` und ergänzt
`id,created_by,created_at,entry_hash`. Die `effect`-Struktur enthält
`operation,payload,source,target,postings,details`; Korrekturen enthalten die
exakten negierten früheren Buchungslinien zusätzlich zu den neuen Linien.

Ein Bericht enthält `confirmed_income,confirmed_expenses,confirmed_surplus,
confirmed_output_vat,confirmed_input_vat` unter `totals`, außerdem einzelne
Buchungslinien, Kategorien, Anlagen, Quellenmanifest, Perioden und Klärungsfälle.
`euer_surplus` und `vat_balance` bleiben bei offenen Fällen `null`.
`complete_for_recorded_sources` beschreibt ausschließlich erfasste Quellen.
`coverage_start` nennt den erklärten Buchführungsbeginn; eine nur teilweise
gedeckte Jahresperiode bleibt ein ausdrücklicher Klärungsfall. Dies ersetzt
weder den Abgleich eines echten Unternehmensjahres noch fehlende Sonderregeln.
