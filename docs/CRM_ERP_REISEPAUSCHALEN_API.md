# Reisen und Pauschalen 2026 – Implementierungsvertrag

Stand 03.11.2026. Implementierter Backendvertrag; vollständige Produktabnahme
einschließlich des neuen v5-Lohnlinks wird gesondert nachgewiesen.
Fachlicher Regelumfang: [Reiseentwurf](CRM_ERP_REISEPAUSCHALEN_ENTWURF_2026.md).
Geldbeträge sind ganzzahlige EUR-Cent; Sekunden und Revisionen sind ganze Zahlen.
Alle Fach-IDs und `request_id` sind 32 kleingeschriebene Hexzeichen. Datum:
`YYYY-MM-DD`; Zeitpunkte: RFC3339 mit ausdrücklichem Offset. Fehlende Fakten
bleiben offen, statt angenommene Nullwerte oder steuerfreie Beträge zu erzeugen.

## Zugriff und gemeinsame Antworten

Feature `travel_allowances`, Capability `business_travel_allowances`, Fachmodul
`personnel`. Eigene Reisen: frische Mitarbeiterzuordnung plus `time.own` oder
Personalrecht. Fremde Reisen: `personnel.read/write`; Prüfen/Freigeben zusätzlich
`personnel.approve`. Eigene oder selbst eingereichte Reisen können nicht selbst
freigegeben werden. Exporte verlangen `personnel.export`, soweit es kein eigener
zulässiger Beleg ist. Zahlungsbefehle verlangen `personnel.approve`,
`finance.write` und `accounting.prepare`, außerdem tatsächliche Finanzaktivierung.
Kein pauschaler Owner-Schalter überspringt Fremdprüfung oder Quellenintegrität.

`GET /business/personnel/travel/sources?employee_id=ID`:

```json
{
  "employee": {"id":"ID", "user_id":"USER_ID", "name":"Vorname Nachname"},
  "rights": {"read":true,"write":true,"approve":false,"export":true,"payments":false},
  "active":true, "readonly":false, "source_hash":"SHA256",
  "files":[], "projects":[], "sites":[], "expenses":[], "accounts":[], "instance_id":null
}
```

Die Auswahl enthält nur aktuell lesbare Quellen. Dateiobjekte enthalten `id`,
`employee_id`, `filename`, `sha256`, `purpose`, `owner_visible`. Es werden die
bestehenden unveränderten Personaloriginale unter `/personnel/files` verwendet;
eigene Reisebelege benötigen den dortigen eigenen Auslagenbelegzugriff.
Projektobjekte enthalten `id,name`, nur tatsächliche zulässige Projektzuordnung.
`accounts` und feste `instance_id` werden nur bei tatsächlichem Zahlungsrecht
geliefert. Kontoobjekte enthalten mindestens `id,name,revision,currency,active`;
Geldkonto, Revision und feste Unternehmens-ID sind bei jeder Zahlung Pflicht.
Stätten-/Auslagenreferenzen enthalten zusätzlich `revision,content_hash`.

`GET /business/personnel/travel/catalog` liefert
`rule_version,rule_hash,table_hash,effective_from,effective_to,rates,site_kinds,
meal_kinds,meal_providers,transport_kinds,claim_methods`. Jede Katalograte hat
`id,country,region,full_minor,short_minor,lodging_minor`; Inland ist `de_2026`.
Die veröffentlichten 214 Auslands-Betragszeilen verwenden `tr2026_001` bis
`tr2026_214`. Ein nicht genannter Staat wird ausdrücklich mit Ersatzlandgrund
erfasst, nicht durch unbekannten Freitext automatisch Luxemburg zugeordnet.

Listen liefern `items,employee_id,rights,active,readonly`. Detailantworten sind
`item,rights,active,readonly,source_hash`, historische Listen `items,id,employee_id`.
Der äußere `source_hash` bindet aktuelle Quellen. `item.content_hash` bezeichnet
die unveränderliche einzelne Fachfassung; beide sind nicht austauschbar.
Fähigkeiten sind aktuell, Fachfassungen unveränderlich. Ein Berechnungsfehler
ist ein benannter `blocker`; ein technischer HTTP-Fehler ist kein Nullanspruch.

## Befehlsquittung und unklare Antwort

Jeder POST besitzt `request_id,employee_id`; Ziel-ID bei Erstanlage erzeugt der
Client vor dem Versand. Auftrag und Nonce bleiben nur im privaten RAM.
Statusroute: `GET /business/personnel/travel/requests/{request_id}`. Sie prüft
den tatsächlichen Akteur und heutige Mitarbeiter-/Quellenrechte. Antwort:

```json
{
 "request_id":"NONCE","actor_id":"USER_ID","employee_id":"EMPLOYEE_ID",
 "operation":"trip.save","target_kind":"trip","target_id":"TRIP_ID",
 "revision":1,"request_hash":"SHA256","result_hash":"SHA256",
 "confirmed":true,"result":{"id":"TRIP_ID","revision":1,"employee_id":"EMPLOYEE_ID"}
}
```

`request_hash` = SHA256 des UTF-8-JSON aus
`canonical([operation,target_kind,target_id,exakter_originalbody])`.
`result_hash` = SHA256 von `canonical(result)`. Die Quittung ist an Akteur,
Mitarbeiter, Operation, Ziel und angenommene Revision gebunden; der Server
rekonstruiert das Ergebnis aus der ursprünglichen Fachfassung. Er speichert
keine zusätzliche vollständige Kopie privater Reiseangaben im Anfragejournal.
Gleiche Nonce mit anderem Inhalt: 409. Ein unbestätigtes 404 löscht keinen Auftrag.
Status wird vor ausdrücklichem identischem Retry abgefragt; nur bei frischen
Schreibrechten und Aktivierung wird exakt dieselbe Anfrage wiederholt. Kein
automatischer Zahlungsretry. Eine angenommene Quittung ist nach Modulpause
weiter lesbar, sofern die heutigen Leserechte bestehen. Sitzungs-/Mitarbeiter-
oder Hintergrundwechsel verwirft private unbestätigte RAM-Aufträge.

Zeitauflösung: `GET /business/personnel/travel/time-options?local=YYYY-MM-DDTHH:mm&timezone=IANA`
liefert `{local,timezone,options:[{instant,offset,label}],valid}`. Die tatsächliche
IANA-Regelprüfung liefert null, eine oder zwei Möglichkeiten; bei Sommerzeitlücke
wird keine Zeit erfunden, bei doppelter Zeit wählt der Benutzer ausdrücklich.
Diese Auflösung speichert keine Reise und erzeugt keinen Geldfluss.

## Stättennachweise

`GET /sites?employee_id=ID`, `GET /sites/{id}`, `GET /sites/{id}/history`.
`POST /sites` (`site.save`) mit:

```text
request_id, employee_id, id, revision, status(active|void),
details:{name,kind(home|first_workplace|external_fixed|mobile|wide_area),
         address,rate_id,timezone,effective_from,effective_to,
         assignment_basis,regular_days_per_week,
         history_complete_from,prior_visit_dates,source_file_ids,
         frequency_periods?:[{from,to,days_per_week,source_file_ids}]},
correction_reason
```

Neue Stätte erwartet Revision 0, danach die aktuelle Revision. Ende darf null
sein; ansonsten inklusive Datumsgrenzen. `regular_days_per_week` ist die
ausdrücklich belegte tatsächliche Einsatzhäufigkeit, nicht aus Projektstunden
erraten. Die Vorgeschichte wird mit Original und Vollständigkeitsbeginn
gebunden. Widersprüche, unvollständige Dreimonatsvorgeschichte und ungeprüfte
erste Tätigkeitsstätte verhindern die endgültige steuerliche Freigabe.
`assignment_basis` ist ein begründeter Freitext zur belegten Zuordnung, kein
pauschaler Schalter „steuerfrei“. Stättenname/Anschrift sind private Personaldaten.
Ohne `frequency_periods` gilt die belegte Häufigkeit über die ganze Historie als
konstant. Änderungen benötigen lückenlose, mit Originalen gebundene Phasen.
Zwei→drei Tage startet erst die Dreimonatsfrist; drei→zwei stoppt eine bereits
laufende Frist nicht. Genau 28 vollständig besuchsfreie Tage starten neu.

## Reise und tatsächliche Einzelereignisse

`GET /trips?employee_id=ID`, `GET /trips/{id}`, `GET /trips/{id}/history`.
`POST /trips` (`trip.save`) mit:

```text
request_id, employee_id, id, revision,
details:{purpose,project_id,departed_at,returned_at,timezone,
         source_file_ids,home_site_ref,first_workplace_ref,
         segments:[{id,from,to,site_ref,activity(work|transit|stay),
                    transport(ground|flight|ship),necessary_stopover}],
         overnights:[{id,date,site_ref,claim_method(none|flat|expense),
                      provided_by(employee|employer|third_party_free),expense_ref,
                      expense_receipt_file_id?,
                      accommodation_kind?(lodging|vehicle|sleeper_train|ship_cabin),
                      other_lodging_started_or_finished?:boolean}],
         meals:[{id,date,kind(breakfast|lunch|dinner),
                 provider(employer|employer_arranged|independent_third_party|self),
                 offered,is_meal,price_minor,employee_paid_minor,
                 replacement_for,source_file_ids}],
         expense_refs,expense_allocations?:[{expense_ref,receipt_file_id,
           kind(transport|lodging|incidental),business_minor,private_minor,
           provided_minor,review_note}],transport_facts?:[],
         requested_meal_minor,requested_lodging_minor,
         tax_choice(tax_free_only|flat_25|individual),private_intervals},
correction_reason
```

Referenzen auf gespeicherte Fachquellen sind `id,revision,content_hash`;
Originale zusätzlich mit Mitarbeiter und SHA256 gebunden. Nicht verwendete
optionale Referenzen sind null, Listen leer. Betragswünsche werden ausdrücklich
erfasst; sie ändern keine gesetzlichen Tagessätze. Bei `tax_free_only` kann die
UI einen belegten errechneten Vorschlag übernehmen, muss ihn aber sichtbar
bestätigen. Öffentliche Projekte erhalten weder Reiseroute noch Mahlzeitdaten.
Sommerzeitoffset muss zur angegebenen IANA-Zone passen. Orts-/Zeitketten dürfen
keine Lücken oder Überlappungen haben; echte Datumsgrenzen bleiben als konkrete
Orts-/Tageszuordnung in der Berechnung sichtbar. Jede Außenübernachtung wird
gesondert belegt, auch ohne beantragte Übernachtungspauschale.
Eine Nacht muss durch einen tatsächlichen Ortsabschnitt über örtliche Mitternacht
getragen werden. Wohnung oder erste Tätigkeitsstätte sind keine Außenübernachtung.
Für eine normale Pauschale ist die Unterkunftsart ausdrücklich erforderlich;
gewöhnliche Fahrzeugübernachtung ist ausgeschlossen. Die eng begrenzte Ausnahme
für Schlafwagen/Schiffskabine benötigt belegten Beginn oder Ende der Übernachtung
in anderer Unterkunft. Ein Hotelbeleg darf mehrere Nächte belegen, wird aber nur
einmal als tatsächlicher Aufwand erstattet.

Flug-/Schiffsnachweise folgen dem vollständigen
[Transportvertrag](CRM_ERP_REISE_TRANSPORT_VERTRAG_2026.md). Sie binden vorhandene
Abschnitts-IDs, tatsächliche Flughäfen/Häfen, notwendige Zwischenübernachtungen,
Besatzungsstatus/Hochseeabschnitte und Originale. Es gibt kein frei wählbares
Tagesratenfeld. Die eigene Wohnung ist kein Flughafen-/Hafennachweis.

`expense_allocations` teilt jede ausgewählte Originalposition vollständig auf:
`business_minor + private_minor + provided_minor = Originalbetrag`. Nur der
belegte betriebliche Anteil erhöht die erstattbare Arbeitnehmerauslage. Alte
Anträge müssen unabhängig genehmigt sein; bereits erstattete Beträge werden
einmal als bezahlt gebunden. Die Originalreservierung sperrt eine zusätzliche
Erstattung im alten Personalweg. Bereits erstattete private/gestellte Anteile
benötigen Rückzahlung oder eigenständige Lohnkorrektur.

`replacement_for` verweist auf eine Mahlzeit desselben Tages und derselben Art.
Ursprüngliche und vom Arbeitgeber bereitgestellte Ersatzmahlzeit werden gemeinsam
gegen die 60-EUR-Grenze geprüft und lösen höchstens eine Kürzung aus. Ein eigener
privater Ersatzkauf mindert die Arbeitgeberkürzung nicht. Eigenentgelte bleiben
bei der tatsächlich verknüpften Mahlzeit.

`POST /trips/{id}/submit` (`trip.submit`) bindet `request_id,employee_id,revision,
source_hash,confirmed:true`. `POST /trips/{id}/reject` (`trip.reject`) bindet
zusätzlich `reason`. Korrektur erfolgt als neue Draft-Fassung; frühere eingereichte,
abgerechnete und ausgezahlte Fassungen bleiben unverändert. Direkter Sprung von
einer eigenen Erfassung in eine eigene Genehmigung ist nicht zulässig.

## Vorschau, Freigabe und historische Abrechnung

`POST /settlements/preview` ist rein lesend und trägt keine Nonce:

```text
employee_id,trip_refs,period_from,period_to,settlement_unit,
tax_choice,requested_meal_minor,requested_lodging_minor,
correction_of,review_note,payroll_month?:YYYY-MM|null
```

`settlement_unit` ist `trip` oder `combined_period` und bindet die ausdrücklich
gewählte Abrechnungseinheit. Mehrere Reisen desselben Tages werden zusammen
gerechnet; es entsteht kein mehrfacher Tageshöchstbetrag. Antwort:

```text
employee_id,source_hash,preview_hash,rule_version,rule_hash,table_hash,
trip_refs,site_refs,expense_refs,
days:[{date,rate_id,country,region,claim_kind,absence_seconds,
       full_minor,base_minor,meal_reduction_minor,meal_allowance_minor,
       lodging_allowance_minor,benefit_in_kind_minor,letter_m,
       three_month:{started_on,expires_on,reset_on,eligible},
       reasons:[{code,text,source}],sources}],
totals:{meal_base_minor,meal_reduction_minor,meal_allowance_minor,
        lodging_allowance_minor,expense_allowance_minor,expense_already_paid_minor,
        requested_minor,tax_free_minor,
        flat_taxable_minor,individual_taxable_minor,benefit_in_kind_minor,
        already_paid_minor,remaining_minor,overpaid_minor},
expense_items:[{expense_ref,receipt_file_id,receipt_sha256,kind,date,
               business_minor,private_minor,provided_minor,already_paid_minor,review_note}],
transport_sources:[{trip,days,calendar_days,blockers,facts_hash,
                    transport_rule_version,transport_rule_hash}],
blockers:[{code,text,source_ref}],payroll_required,can_approve,can_pay
```

`POST /settlements` (`settlement.approve`) ergänzt `id,request_id,revision,
source_hash,preview_hash,confirmed:true` zu den Vorschauangaben. Quelle,
Mitarbeiter+Tag, tatsächliche Fremdfreigabe und bisherige Quellenbelegungen werden
in derselben Schreibtransaktion geprüft. Vorschau reserviert nichts. Neue
Quellen oder konkurrierende Tagesfreigabe machen eine alte Vorschau unbrauchbar.
`GET /settlements`, `GET /settlements/{id}`, `GET /settlements/{id}/history`,
`GET /settlements/{id}/export?revision=N&format=json|pdf` verwenden unveränderte
historische Snapshotbytes. Eine Korrektur verweist auf die alte Abrechnung und
gleicht bereits erfolgte Geldflüsse ausdrücklich ab.
Standard ist `de_travel_2026_v2`; `de_travel_2026_v1` bleibt über den eingefrorenen
eigenen Rechenkern historisch reproduzierbar. V1 enthält die neuen v2-Felder
nicht. Neue Originale werden nicht durch die Erweiterung alter Hashes umgedeutet.

Steuerpflichtige Mehrbeträge benötigen den ausdrücklich vorgesehenen Zuflussmonat
`payroll_month`; Sachbezug und M folgen dem tatsächlichen Mahlzeitenmonat.
`can_approve` bedeutet vollständig geprüfte Reisefakten, nicht bereits verarbeitete
Lohnsteuer. `payroll_required` hält diese Verarbeitung getrennt sichtbar.
Unveränderliche historische `can_pay`-Werte bleiben der damalige Stand; der
Zahlungswriter prüft den heutigen vollständigen v5-Lohnbezug erneut.

## Tatsächliche Zahlung und öffentliche Finanzquelle

`POST /payments` (`payment.record`) mit:

```text
request_id,employee_id,id,revision,action(record|adopt_legacy|correct|void),settlement_ref,
instance_id,account_id,account_revision,
kind(reimbursement|repayment),paid_on,amount_minor,
reference,reference_file_id,source_hash,correction_reason,confirmed:true,
legacy_payment?:{expense_ref,payment_index,payment_hash}|null
```

Neue Zahlung erwartet Revision 0; eine Änderung erwartet die aktuelle Revision.
`correct` und `void` verlangen neue Begründung und Originalnachweis. Ein falsch
erfasster Datensatz wird nachvollziehbar berichtigt oder ungültig gemacht; er
wird nicht als angeblich tatsächlich erfolgte Rückzahlung umetikettiert. Bereits
in EÜR verwendete historische Quellen verlangen anschließend deren ausdrückliche
Korrektur. Die ursprüngliche Finanzquelle bleibt unter ihrer Revision abrufbar.
`void` bewahrt die ursprünglichen Zahlungsdaten und liefert in der aktuellen
öffentlichen Quelle `cash_movements:[]`. Eine tatsächliche Rückzahlung ist stets
eine eigene `repayment`-Bewegung. Korrektur/Aufhebung darf bestehende Rückzahlungen
nicht größer als die verbleibenden belegten Auszahlungen werden lassen.
Altes und neues Geldflussdatum unterliegen den tatsächlichen EÜR-Periodensperren.

`adopt_legacy` ergänzt ausschließlich den Finanznachweis einer tatsächlich schon
bestätigten alten Auslagenzahlung. `payment_index` ist der nullbasierte Index in
`expense.payments`, `payment_hash` deren SHA256 über kanonisches JSON. Datum,
Richtung, Betrag und Referenz müssen exakt übereinstimmen; der Nutzer ergänzt
ausdrücklich das tatsächliche Geldkonto und den geschützten Originalbeleg.
Der Server prüft auch die erste historische Auslagenfassung, in der diese Zahlung
auftrat, und ihre unveränderten Originalpositionen. Nur vollständig betriebliche
Auslagen ohne private/gestellte Anteile sind auf diesem Weg zulässig.

Die Übernahme verändert weder alte Personalevents noch den erneut auszahlbaren
Betrag. Jede alte Zahlungsposition darf genau eine Finanznachweis-ID erhalten,
auch nach dokumentarischem Void. `correct` bewahrt `legacy_payment` und sämtliche
ursprünglichen Zahlungsangaben; Konto und zusätzlicher Finanzbeleg dürfen mit
Begründung korrigiert werden. `void` hebt nur diesen Finanznachweis auf und
behauptet keine neue Rückzahlung der alten Auslage.

Nur belegte, tatsächlich erfolgte Zahlungen werden erfasst. Teilzahlungen und
Rückzahlungen besitzen eigene eindeutige IDs; die Summe muss zur verfügbaren
freigegebenen Quelle passen. Eine neue Berechnung erzeugt niemals eine Zahlung.
Bereits erstattete Personal-Auslagen werden referenziert und nicht nochmals
ausgezahlt. Übernommene Belegpositionen sind gegen die alte Auslagenaktion in
beiden Richtungen geschützt. Steuerpflichtige Anteile benötigen einen vollständig
verarbeiteten Lohnbezug; ein noch fehlender Lohnzweig wird nicht still zu einer
steuerfreien Erstattung. Mahlzeiten-Sachbezug und Großbuchstabe M bleiben eigene
unveränderliche Lohnkontoquellen, kein zusätzlicher Bargeldbetrag.

Der private Adapter `travel_payroll_sources.travel_payroll_source` liefert
`tax_free_external_minor`, `flat_taxable_payroll_minor`,
`individual_taxable_payroll_minor`, `benefit_in_kind_non_cash_minor`, `letter_m`
und eindeutige Monats-/Betragszuordnungen mit Quellhash. TravelCash zahlt nur den
steuerfreien Anteil; steuerpflichtige Erstattungsmehrbeträge werden genau einmal
im Lohn ausgezahlt. Sachbezug erhöht die einschlägigen Bruttobasen mit gleichem
Sachbezugs-Nettoabzug. Eine Reisezahlung mit Lohnbedarf benötigt den exakt
passenden angenommenen v5-Lauf; dessen historischer Nachweis wird in der Zahlung
gebunden und bleibt auch nach späterer Lohnkorrektur prüfbar.

`GET /payments?employee_id=ID` bleibt privat. Die getrennte öffentliche
Finanzprojektion unter `GET /personnel/travel/financial/{id}?revision=N` verlangt
ausschließlich frische Finanz-/Buchführungsrechte, keine äußere Personalberechtigung.
Sie verwendet Quellenart `travel_cash`, eine opake Quellen-ID,
Datum, Richtung, Betrag, Quellhash und geprüfte Reisekostenkategorie. Sie enthält
keine Personennamen, Anschriften, Route, Tätigkeit oder Mahlzeit. EÜR kann diese
tatsächliche Geldquelle unter eigenen Finanz-/Buchführungsrechten einordnen;
Pauschalen enthalten keine Vorsteuer. Bankzuordnung betrifft dieselbe bestehende
Geldquelle und erzeugt keinen zweiten Geldfluss.

## Datenhaltung und Integration

Vorgesehene additive Tabellen: `business_travel_sites`, `business_travel_trips`,
`business_travel_settlements`, `business_travel_claims`,
`business_travel_payments`, `business_travel_cash_events`, `business_travel_evidence`,
`business_travel_requests`. Fachfassungen/Quittungen sind append-only; genaue
DDL-Spalten werden Root vor globaler Registrierung übergeben. Reise-, Stätten-
und Personenhistorien bleiben sensibel; nur Cashprojektion ist finanzöffentlich.
Restore prüft die damaligen Originale, Quellenfassungen, Regeln, Berechnungen,
Tagesbelegungen und Zahlungen, nicht heutige Mitarbeiter- oder Stättendaten.
Der neue vollständige Finanzhorizont bindet die tatsächlichen Reisegeldquellen.
Alte Restorebeweise, Lohn-/Personalquittungen und Jahresausgaben bleiben unter
ihren ursprünglichen Versionen lesbar. Root registriert Schema/API, Export,
Privacy, Finanzhorizont, Pakete und Clients nach finalem Vertrag.
