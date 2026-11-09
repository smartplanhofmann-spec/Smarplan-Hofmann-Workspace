# Kilometererstattung – enger additiver Vertrag 2026

Implementierter und gezielt geprüfter Backendvertrag, 09.11.2026. Feature
`travel_private_car_mileage`, Lesesupportmarker `travel_private_car_mileage_read`,
Regel `de_travel_2026_v4_private_car`.
Die bestehende Standardregel v3 und alle historischen Rechenkerne bleiben
unverändert. Neue Kilometerfälle müssen ausdrücklich über die neuen Pfade
angelegt werden. Dies ist eine Mitarbeitererstattung, keine Buchung eigener
Fahrten des Einzelunternehmers und keine automatische Auszahlung.

## Fachlicher Umfang und Quellen

Eine tatsächlich gefahrene, rein dienstliche Inlands-Rundfahrt pro Person und
Kalendertag im Jahr 2026, mit privat gestelltem Pkw und selbst getragenen
Fahrzeugkosten. Die belegten einzelnen Teilstrecken werden in ganzen Metern
gespeichert. Der Betrag ist `round_half_up(sum(distance_m) * 30 / 1000)` Cent.
Die Rundung erfolgt einmal je vollständiger Fahrt, nicht je Teilstrecke.
Alle Geldbeträge sind ganzzahlig; Eingabebeträge ersetzen keine Strecke.

Die fachlichen Grundlagen wurden am 09.11.2026 über die öffentliche
Web-Recherche gelesen:

- [§9 Abs.1 S.3 Nr.4a EStG](https://www.gesetze-im-internet.de/estg/__9.html):
  berufliche Auswärtsfahrten; alternativ höchster pauschaler BRKG-Kilometersatz.
- [§5 Abs.2 BRKG](https://www.gesetze-im-internet.de/brkg_2005/__5.html):
  höchster Satz für Kraftwagen 30 Cent je gefahrenem Kilometer. Die
  zusätzlichen Regeln für die Erstattung an Bundesbedienstete werden nicht
  als zusätzliche Voraussetzung privater Arbeitgeber übertragen.
- [§3 Nr.16 EStG](https://www.gesetze-im-internet.de/estg/__3.html):
  steuerfreier Arbeitgeberersatz bis zur entsprechenden Werbungskostengrenze.
- [R9.5 Abs.1 und 2 LStH2026](https://amtliche-handbuecher.bundesfinanzministerium.de/lsth/2026/A-Einkommensteuergesetz/II-Einkommen-2-24b/4-Ueberschuss-d-Einnahmen-ueber-die-Werbungsk-8-9a/Paragraf-9/inhalt.html):
  Nachweisunterlagen zum Lohnkonto und Ausschluss des steuerfreien pauschalen
  Ersatzes bei arbeitgeberseitig gestelltem Fahrzeug.

Nicht enthalten sind Pendel-/Familienheimfahrten, Sammelpunkte oder weiträumige
Tätigkeitsgebiete, Dienstwagen, Mitfahrt ohne eigene Fahrzeugkosten, private
Teilstrecken, Ausland, Übernachtung, andere Auslagen/Verpflegungspauschalen,
individuelle Fahrzeugkostensätze und überpauschale Erstattungen. Der enge
Vertrag beansprucht den Personentag exklusiv gegen andere Reiseabrechnungen.
Zwei Abrechnungen für dieselbe Fahrt oder denselben Tag werden verhindert.
Die alten Reise-Lohnadapter übernehmen V4 ausdrücklich nicht: kein M-Merkmal,
kein steuerpflichtiger Betrag, keine zweite Addition zum Nettolohn.

## Neue HTTP-Pfade

Alle Pfade unter `/business/personnel/travel/mileage`:

| Pfad | Methoden |
| --- | --- |
| `/catalog` | GET Metadaten, Satz, Grenzen, Quellen |
| `/sources?employee_id=ID` | GET vorhandene eigene Dateien, Stätten, Rechte, Geldkonten und Quellenhash |
| `/trips?employee_id=ID` | GET ausschließlich V4-Fahrten |
| `/trips` | POST Entwurf oder ausdrückliche begründete Korrektur |
| `/trips/ID`, `/trips/ID/history` | GET genaue V4-Fassung oder Historie |
| `/trips/ID/submit`, `/trips/ID/reject` | POST vorhandener Reise-Aktionsvertrag |
| `/settlements/preview` | POST gebundene Vorschau |
| `/settlements` | POST fremdgeprüfte Abrechnung oder begründete Folgefassung |
| `/settlements?employee_id=ID` | GET ausschließlich V4-Abrechnungen |
| `/settlements/ID`, `/settlements/ID/history` | GET genaue V4-Fassung oder Historie |
| `/settlements/ID/export?format=pdf|json&revision=N` | GET Originalexport |
| `/payments?employee_id=ID`, `/payments/ID`, `/payments/ID/history` | GET zugehörige ursprüngliche TravelCash-Zahlungsnachweise |
| `/payments` | POST bestehender TravelCash-Zahlungsvertrag |
| `/requests/ID` | GET identische ursprüngliche Auftragsquittung |

Die bestehenden allgemeinen Reiselisten filtern V4-Fahrten/-Abrechnungen und
deren private Zahlungen aus. Die neuen Pfade zeigen sie ausdrücklich. Die
öffentlichen vorhandenen Finanz-/Bank-/EÜR-Quellen bleiben vollständig.
Alte Pfade dürfen einen V4-Fall nicht in v3 umschreiben. Der Lesesupportmarker
zeigt den installierten V4-Vertrag unabhängig von der UI-Schreibauswahl an.
Fehlende Schreib-Featurekennung bedeutet keine neue Erfassungsmöglichkeit;
Originale bleiben bei vorhandenem Lesesupport nach ihren Rechten lesbar.
Der Marker gewährt selbst keinerlei Personen-, Projekt- oder Dateirechte.
Zusätzlich gelten `active`, `readonly` und frische Rechte. Sämtliche
Entscheidungen benötigen frische Rechte.

## Fahrt erfassen

Der POST erhält genau die bisherigen Hüllenfelder
`request_id`, `employee_id`, `id`, `revision`, `details`, `correction_reason`.
Alle IDs sind 32 kleine Hexzeichen; `id` wird bereits vor dem ersten POST
erzeugt. Neuanlage `revision:0`, sonst aktueller Stand und nichtleerer Grund.
`details` enthält genau:

```json
{
  "purpose": "Materialaufnahme bei Kunde",
  "project_id": null,
  "departed_at": "2026-10-26T08:00:00+01:00",
  "returned_at": "2026-10-26T13:00:00+01:00",
  "timezone": "Europe/Berlin",
  "home_site_ref": {"id":"11111111111111111111111111111111","revision":1,"content_hash":"HASH64"},
  "first_workplace_ref": null,
  "source_file_ids": ["44444444444444444444444444444444","55555555555555555555555555555555"],
  "mileage": {
    "schema_version": 1,
    "vehicle_kind": "private_car",
    "vehicle_registration": "SYNTHETISCH-1",
    "vehicle_file_id": "44444444444444444444444444444444",
    "declaration_file_id": "55555555555555555555555555555555",
    "employee_bears_vehicle_costs": true,
    "no_employer_vehicle": true,
    "only_business_travel": true,
    "no_commuting_or_family_home": true,
    "no_collection_point_or_wide_area": true,
    "no_other_reimbursement": true,
    "legs": [
      {
        "id": "66666666666666666666666666666666",
        "departed_at": "2026-10-26T08:00:00+01:00",
        "arrived_at": "2026-10-26T09:00:00+01:00",
        "from_site_ref": {"id":"11111111111111111111111111111111","revision":1,"content_hash":"HASH64"},
        "to_site_ref": {"id":"22222222222222222222222222222222","revision":1,"content_hash":"HASH64"},
        "distance_m": 50000,
        "evidence_file_id": "55555555555555555555555555555555"
      },
      {
        "id": "77777777777777777777777777777777",
        "departed_at": "2026-10-26T12:00:00+01:00",
        "arrived_at": "2026-10-26T13:00:00+01:00",
        "from_site_ref": {"id":"22222222222222222222222222222222","revision":1,"content_hash":"HASH64"},
        "to_site_ref": {"id":"11111111111111111111111111111111","revision":1,"content_hash":"HASH64"},
        "distance_m": 50000,
        "evidence_file_id": "55555555555555555555555555555555"
      }
    ],
    "review_note": "Vollständige Originalstrecke, privater Pkw und fehlende anderweitige Erstattung belegt."
  }
}
```

`HASH64` steht nur im Beispiel für den tatsächlichen 64-stelligen Hash.
`purpose`: 1–1000 Zeichen, Kennzeichen 1–32, Prüfvermerk 1–2000.
`project_id` ist null oder ein aktuell berechtigtes Projekt. Fahrzeug-,
Erklärungs- und alle Streckennachweise gehören zu `source_file_ids` (1–100)
und sind private `personnel`-Originaldateien genau dieser Person.
`first_workplace_ref` ist null nur wenn keine aktuelle erste Tätigkeitsstätte
belegt ist; ansonsten bindet er die eindeutige aktuelle erste Tätigkeitsstätte.

1–100 geordnete Teilstrecken, jeweils 1–2.000.000 ganze Meter. Die Ortsfolge
muss lückenlos sein; die Fahrt beginnt und endet an derselben Wohnung oder
ersten Tätigkeitsstätte. Zwischenpunkte sind ausschließlich belegte inländische
`external_fixed`-Stätten. Jede Teilstrecke muss einen auswärtigen Endpunkt
haben; Wohnung–erste Tätigkeitsstätte ist gesperrt. Die Zeitpunkte haben echte
passende Berlin-UTC-Offsets, liegen im gleichen 2026-Kalendertag und überlappen
nicht. Erster Abfahrts- und letzter Ankunftszeitpunkt entsprechen der Hülle.
Stätten und Belege werden vollständig mit ihren historischen Originalen gebunden.
Fehlende Bool-Bestätigungen dürfen als Entwurf erfasst werden, sperren aber die
Abrechnung. Kein Feld ist im Client automatisch vorbestätigt.

## Abrechnung, Quittung und Zahlung

Vorschau und Annahme behalten die bestehenden Reise-Hüllenfelder. Genau eine
eingereichte V4-Fahrt in `trip_refs`; `settlement_unit:"trip"`,
`tax_choice:"tax_free_only"`, `requested_meal_minor:0`,
`requested_lodging_minor:0`, `payroll_month` fehlt oder ist null.
`period_from` und `period_to` sind beide der Original-Fahrttag.
`review_note` ist ein nichtleerer unabhängiger Prüfvermerk. Bei Annahme kommen
`id`, `request_id`, `revision`, `source_hash`, `preview_hash`, `confirmed:true`
hinzu. `correction_of` ist null oder die genaue aktuelle eigene Abrechnungsfassung.
Korrekturen behalten Person, ursprüngliche Fahrt-ID und Tag; vorherige tatsächliche
Zahlungen bleiben unverändert. Nach einer Minderkorrektur wird ein Überzahlungsbetrag
ausgewiesen; nur eine ausdrücklich belegte Rückzahlung vermindert den Geldfluss.

Reise-/Abrechnungs-/Zahlungsantworten bleiben bestehende Auftragsquittungen mit
`result` und bindenden Auftrags-/Ergebnishashes. V4-Abrechnungen sind echte
`kind:"settlement"`-Originale, keine fingierten EUR-Auslagen. In ihrer Berechnung
stehen `mileage_items` und ganzzahliges `totals.mileage_distance_m` sowie
`totals.mileage_allowance_minor`; Tagesverpflegung, Unterkunft, Belegauslagen,
Sachbezüge und steuerpflichtige Erstattungen sind 0. `payroll_required:false`
und `days[0].letter_m:false`. Die steuerfreie Gesamtsumme ist genau einmal der
Kilometerbetrag. Der Tagesanspruch und die gefahrene Originalquelle werden
gegen andere Abrechnungs-IDs gesperrt.

Die Berechnung liefert die bisherigen gemeinsamen Metadaten, Tage, Summen,
Blocker sowie `can_approve`/`can_pay`. Jedes `mileage_items`-Element enthält
`trip_ref`, `leg_id`, `from_site_ref`, `to_site_ref`, `distance_m`,
`rate_minor_per_km:30`, `evidence_file_id`, `evidence_sha256`. Einzelteilbeträge
werden nicht gerundet oder als erfundene Einzelnettos ausgewiesen.

Verbindliche Ergebnisfelder für den neuen reinen Kern:

- Top-Level genau `rule_version`, `rule_hash`, `table_hash`, `days`,
  `expense_items`, `transport_sources`, `ground_calendar_sources`,
  `mixed_program_sources`, `mileage_items`, `totals`, `blockers`,
  `payroll_required`, `can_approve`, `can_pay`. Die vier alten Quellenlisten
  vor `mileage_items` sind leer.
- Genau ein Tag mit `date`, `country:"Deutschland"`, `base_minor:0`,
  `meal_reduction_minor:0`, `meal_allowance_minor:0`,
  `lodging_allowance_minor:0`, `benefit_in_kind_minor:0`, `letter_m:false`,
  `mileage_allowance_minor`.
- `totals` hat die bisherigen Schlüssel `meal_base_minor`,
  `meal_reduction_minor`, `meal_allowance_minor`, `lodging_allowance_minor`,
  `expense_allowance_minor`, `expense_already_paid_minor`, `requested_minor`,
  `tax_free_minor`, `flat_taxable_minor`, `individual_taxable_minor`,
  `benefit_in_kind_minor`, `already_paid_minor`, `remaining_minor`,
  `overpaid_minor`, ergänzt um `mileage_distance_m`, `mileage_allowance_minor`.
  Alle fachfremden Beträge sind 0; angeforderter/steuerfreier Betrag ist
  der Kilometerbetrag. `remaining_minor=max(0,amount-paid)`,
  `overpaid_minor=max(0,paid-amount)`.
- Fehlende positive Bool-Erklärungen ergeben je ein Objekt
  `{code:"mileage_<field>_missing",text:"…",source_ref:trip_ref}` in `blockers`.
  `can_approve` ist genau die Abwesenheit von Blockern; `can_pay` verlangt
  zusätzlich einen positiven Restbetrag. Strukturell falsche Daten,
  unbekannte Fahrzeug-/Gebiets-/Zeitzonenfälle, unzulässige Routen oder
  nicht ganzzahlige Mengen werden mit 400 abgewiesen.

Start/Ziel ist genau eine der gebundenen Wohn-/ersten Tätigkeitsstätten;
die jeweils andere darf nicht als Umweg in der Route auftreten. Alle weiteren
Orte sind `external_fixed`. Die Originale müssen aktiv, in Deutschland und
am betreffenden Tag gültig sein. Mindestens ein auswärtiger Ort ist nötig.
Die reine Berechnung verwendet genau die gespeicherten Originale; die API
prüft zusätzlich die aktuelle Version bei neuen Schreibvorgängen.

Die bestehende TravelCash-Zahlung wird erst nach unabhängiger Abrechnung und
ausdrücklicher Bestätigung tatsächlich erfolgter Überweisung erfasst. Gleiche
Beleg-/Bankidentität darf nicht doppelt verwendet werden. Privater Strecken-
und Fahrzeuginhalt gehört nicht in öffentliche Finanzquellen. Teilzahlung,
Rückzahlung, Korrektur, Bankabgleich und EÜR verwenden den bestehenden Geldweg.

## Verifikation

Geprüft: unabhängige Cent-/Rundungsvektoren, tatsächlicher eigener Antrag und
fremde Freigabe, falsche Person/Stätte/Tag/Fahrzeug/Privatanteile, fehlende
Erklärungen, doppelte Fahrt/Tag/Belegidentität, aktuelle Rechte und verlorene
Antwort, volle Originalhistorie/PDFs, Teilzahlung/Korrektur/Rückzahlung/EÜR,
PostgreSQL-Konkurrenz und tatsächlicher Dump/Restore. Alte v1/v2/v3-Originale
und alle 32 bisherigen Kernhashes bleiben unverändert. Details und erhaltene
Fehlversuche: [Backendprüfbericht](CRM_ERP_KILOMETERERSTATTUNG_BACKEND_PRUEFUNG_2026.md).
Browser- und native Bedienabnahme werden separat mit diesem Vertrag integriert.
