# P4 Anspruchsfakten – neuer isolierter API-Vertrag

Stand 03.11.2026, eigener Fachservice und Routen zentral registriert; unabhängige private Gegenprüfung und gemeinsame Payroll-Integration laufen noch. Eigene Dateien `business_payroll_entitlements.py`, `payroll_entitlements_2026.py`, `payroll_holidays_2026.py`; keine Änderung von P2/P3a. Gemeinsame spätere Payroll-Regel mit P3b: `de_2026_segments_entitlements_v5`, Eingabe `source_schema_version:3` / `calculation_case_ref`. Die Gesamtfall- und Versionsdispatch-Dateien gehören dem P3b-Agenten.

## Endpunkte und Rechte

Basis `/business/payroll/entitlements`: GET Liste mit `employee_id` und optional `kind`, POST bestätigen; GET `/sources?employee_id=…`, GET `/{id}`, GET `/{id}/history`; POST `/preview`. Globales frisches `personnel.read` immer, für sämtliche Bestätigungen zusätzlich `personnel.approve`. Originale bleiben private Personalakten; kein Selbstleserecht über `time.own`.

Feature `payroll_entitlements`, Modul `business_payroll_entitlements`. Ein bereits angenommener Auftrag bleibt bei deaktiviertem Personalmodul mit frischen Lesefreigaben und Freigaberecht wiederholbar. Neue Aufträge benötigen aktives Modul und die passende Schemafähigkeit. Keine Fachmeldung, Zahlung oder tatsächliche Projektzeit entsteht dabei.

## DTO

Faktarten `sickness_history`, `regular_absence`, `vacation_reference`, `unpaid_continuation`. Alle Fakten haben eigene 32-stellige Hex-ID, aufsteigende Revision, `active|void`, `effective_from/effective_to`, Vorgängerhash, kanonische Details, Originale, eingefrorene Quellen, eigenen Plan und Vorschauhash.

`details` hat exakt:

```text
{
  case_key: 32hex,
  employment_terms_ref: {id,revision,content_hash},
  work_schedule_refs: [ref],
  preparation_refs: [ref],
  agreement_refs: [ref],
  sickness_history_ref: ref|null,
  input: typisierter Eingang der jeweiligen reinen Anspruchsfunktion,
  verification_note: string
}
```

`case_key` bezeichnet einen fachlichen Fall und bleibt bei Korrekturen gleich. Mehrere Urlaubsvorgänge in einem Monat sind möglich; die spätere Gesamtfall-Komposition prüft doppelte/überlappende Vergütung. `agreement_refs` mindestens eins; Plan-/Vorbereitungslisten können für externe historische Vorzeiten leer sein. Für aktuelle regelmäßige Ausfallvergütung und Urlaub müssen die betreffenden tatsächlichen Sollpläne und Monatsvorbereitungen gebunden werden. Krankheitstage werden für ihre Vergütung an eine konkrete `sickness_history_ref` gebunden; ein freies `entitled:true` umgeht keine 42-Tage-Grenze.

Alle Eingänge sind exakt typisiert; zusätzliche freie Brutto-/Netto-/Steuer-/SV-Tagefelder werden abgewiesen. Die ausführbaren Feldlisten stehen unmittelbar in den vier Funktionen in `payroll_entitlements_2026.py`; strukturierte Clientformen werden vor zentraler Freischaltung ergänzt. Ein dortiger `evidence_refs`-Eintrag ist ein Personaldateioriginal `{id,revision:1,content_hash}`. Personaldateien sind unveränderlich; eine ersetzende Datei hat eine neue ID. Jede im Eingang verwendete Originalreferenz muss in `source_file_ids` enthalten sein und zum selben Mitarbeiter gehören.

### Konkrete Eingänge für strukturierte Clients

`sickness_history.input`:

```text
employment_from, employment_to:null|ISO, pay_basis:monthly|hourly
complete_from, complete_through, history_evidence_refs:[fileRef]
episodes:[{
  id:32hex, from:ISO, to:ISO,
  onset:before_work|during_work|non_workday,
  first_scheduled_day:null|ISO, continuation_group:32hex,
  recovery_before:true, unculpable:true, evidence_refs:[fileRef]
}]
```

`continuation_group` ist eine private Fortsetzungsfallkennung; die Oberfläche zeigt den zugehörigen belegten Zeitraum, keine Diagnose. Die beiden bestätigten Voraussetzungen ersetzen keine Prüfung unbekannter Fälle: `false` benötigt einen weiteren Regelzweig. Stundenlohn-AU am freien Tag benötigt den ersten tatsächlich ausgefallenen planmäßigen Arbeitstag; alle anderen Fälle verwenden `first_scheduled_day:null`. Ergebnis `episodes` enthält für jeden Originalfall `episode_id,continuation_group,from_date,to_date,count_from,waiting_period_end,entitlement_from/to:null|ISO,entitlement_calendar_days,first_day_remaining_regular_wage:null|ISO,reset_reason,twelve_month_anchor,prior_used_days,remaining_days,evidence_refs`.

`regular_absence.input`:

```text
kind:public_holiday|sickness|first_sickness_day_regular_wage
hourly_rate_minor:int, evidence_refs:[fileRef]
days:[{
  date:ISO, scheduled_regular_seconds:int, worked_regular_seconds:int,
  entitled:bool, absence_is_only_cause:bool,
  holiday_adjacent_unexcused:null|bool, evidence_refs:[fileRef]
}]
```

Die Oberfläche leitet Stundensatz, Soll-/Istzeit und Krankheitsanspruch aus den gewählten Quellen ab. Der Server prüft diese Werte erneut. `entitled` ist kein freier Übersteuerungsschalter. Beim Feiertag ist `holiday_adjacent_unexcused` ausdrücklich zu belegen, bei anderen Arten null. Tatsächlich begonnene Arbeit benötigt positive freigegebene Istzeit; volle Krankheits-/Urlaubstage dürfen keine gleichzeitig geleistete Arbeit verschweigen. Ergebnis `days[{date,paid_absence_seconds,actual_work_seconds,evidence_refs}]`, `paid_absence_seconds`, `gross_minor`, `ratio{numerator,denominator:3600}`, `actual_project_time_modified:false`.

`vacation_reference.input`:

```text
vacation_from, vacation_to, in_kind_daily_minor:int, evidence_refs:[fileRef]
reference_days:[{
  date:ISO, contractual_workday:bool, base_earnings_minor:int,
  overtime_earnings_minor:int, protected_reduction_minor:int,
  permanent_raise_minor:int, evidence_refs:[fileRef]
}]
vacation_days:[{date:ISO,scheduled_regular_seconds:int,evidence_refs:[fileRef]}]
```

Die Referenz umfasst genau 91 Kalendertage vor dem ersten tatsächlichen Urlaubstag und einen gleichbleibenden vertraglichen Wochenrhythmus. Sie wird als belegte Tabelle mit Originalauswahl dargestellt; fehlende Werte sind nicht still null. Ergebnis `reference_from/to`, `reference_components`, `workday_average{numerator,denominator}`, `vacation_days:[ISO]`, `paid_absence_seconds`, `in_kind_cash_compensation_minor`, `gross_minor`, `due_before`, `actual_project_time_modified:false`. Bei mehrmonatigem Urlaub verwendet die neue Gesamtkomposition den exakten Quotienten und die tatsächlich auf den Monat entfallenden Tage; Monatslohn wird nicht zusätzlich bezahlt.

`unpaid_continuation.input`:

```text
from, to, employment_to:null|ISO,
employment_continues:true, no_wage_claim:true,
intervening_paid_days:[], evidence_refs:[fileRef],
exceptions:[{kind,from,to,employment_scope:this_employment,evidence_refs:[fileRef]}]
```

Ausnahmecodes: `sickness_benefit,private_sickness_benefit,injury_benefit,social_compensation_sickness_benefit,soldier_compensation_sickness_benefit,transition_benefit,care_support_benefit,maternity_benefit,child_raising_benefit,parental_benefit,parental_leave,military_service,civilian_service,care_leave_section_3`. Nur tatsächlich belegte Bezüge/Tatbestände; Krankengeld aus einem anderen Beschäftigungsverhältnis wird hier nicht zugeordnet. Ergebnis `continuation_windows[{from,statutory_deadline,basis}]`, `intervals[{from,to,calendar_days,basis,employment_for_contributions_continues,evidence_refs}]`, `tax_lzz_reduced_by_unpaid_days:false`, `insurance_membership_determined:false`.

Alle Listen werden kanonisch sortiert: Quellen nach ID, Originalreferenzen zusätzlich Revision; Tageslisten nach Datum; AU-Fälle nach Beginn/ID und Ausnahmen nach Beginn/Ende/Art. Der Requesthash bindet weiterhin die tatsächliche ursprüngliche Anfrage vor dieser Normalisierung.

Vorschauanfrage:

```text
{employee_id,employee_revision,kind,details,source_file_ids}
```

Antwort: `{employee_id,kind,source_snapshot,source_hash,plan,preview_hash,can_confirm,can_calculate,can_write,can_approve,writes_enabled}`. `can_calculate` bezieht sich allein auf diesen Anspruchsbaustein; es ist keine Freigabe einer vollständigen Nettoabrechnung. Nicht unterstützte Regeln werden vor Annahme präzise gesperrt; P2 kann den offenen Monatsfall weiterhin erfassen.

Bestätigungsanfrage zusätzlich `request_id,revision,id?,status,confirmed:true,preview_hash,correction_reason?`. Die konkrete ursprüngliche Anfrage wird unverändert als `accepted_command` ausschließlich im geschützten Ereignis-Payload gespeichert und gehasht; dieses interne Feld gehört nicht zu API-DTOs. Die technische Quittung enthält nur Fakt-ID/Revision/Hash, keine zweite private Kopie. Quellenprüfung und Restore rekonstruieren die Annahme aus Originalauftrag, `command_hash` und zugehöriger Quittung; damit kann eine später ebenfalls vorhandene Mitarbeiterrevision nicht nachträglich den damaligen Auftrag ersetzen. Gleiche Anfrage liefert die ursprüngliche Fassung auch nach fachlich späteren Änderungen zurück. Gleiche Vorgangs-ID mit anderem Inhalt ergibt 409. Bei `void` bleiben Details, Originale, Quellen und Plan unverändert; der Korrekturgrund und die aktuelle Mitarbeiterrevision sind neu.

## Private Python-Schnittstelle

`PayrollEntitlements(office, clock=None)` mit `sources`, `records`, `get`, `preview`, `save` und `resolve_entitlement_case(actor, employee_id, ref, fresh=True)`.

`validate_entitlement_sources(office, fact)` rekonstruiert historische Quellen; `validate_integrity(office)` prüft Ketten, Originale, Quellen, Pläne und technische Quittungen. Neuverwendung verlangt die aktuellen Fassungen; historisches Replay verlangt die tatsächlich gespeicherten Originale. Quellen ersetzen sich nie still durch neue Mitarbeiter-/Vertrags-/Arbeitsplanfassungen.

`payroll_entitlement_dispatch.build_entitlement_plan(snapshot, rule_version=None)` liefert `schema_version,rule_version,rules_hash,kind,entitlement_kind,input_hash,source_hash,plan_hash` plus typisierte Anspruchsergebnisse. Der gesamte Snapshot, nicht nur seine numerischen Felder, geht in den Quellhash ein. Für historische Rekonstruktion muss die gespeicherte `plan.rule_version` ausdrücklich übergeben werden; eine unbekannte Regel wird nie durch die aktuelle ersetzt.

Neue getrennte Krankheitsverläufe verwenden `de_2026_sickness_v2`; mit ausdrücklich eingegebenen `prevention_cases` wird `de_2026_sickness_phases_v3` gewählt, mit zusätzlichem `employment_commencement` der Beginnzweig `de_2026_sickness_start_v4`. Die übrigen Anspruchsarten behalten v1. Der vollständige Eingabe-/Phasenvertrag und Quellenbezug stehen in [Krankheitsversionen 2026](CRM_ERP_LOHN_KRANKHEIT_VERSIONEN_2026.md). Originale von v1/v2 werden nicht migriert oder neu gehasht. Ein bekannter falscher v1-Stundenlohn-Grenzfall wird ausschließlich für neue Anwendung gesperrt, auch wenn er mittelbar in einer Ausfallvergütung referenziert wird; alte Quittungen, Stornos und historische Wiederherstellung bleiben erhalten.

Snapshot: `{schema_version:1,kind,employee,details,employment_terms,agreements,work_schedules,preparations,sickness_history,source_files,holiday_calendar_hash}`. `sickness_history` ist entweder die vollständige konkret referenzierte Anspruchsfassung oder null. Keine zyklischen Fallreferenzen; nur Vergütungsfakten dürfen auf einen Krankheitsverlauf verweisen. `holiday_calendar_hash` bindet beim Feiertagsfall die 2026-Ländertabelle, sonst null. Die tatsächliche Region kommt aus dem Arbeitsplan. Örtliche Sonderfeiertage benötigen den noch separat zu ergänzenden Gemeindebeleg.

Eigene additive Tabellen `business_payroll_entitlement_events` und `business_payroll_entitlement_requests`, unveränderlich mit SELECT/INSERT-Laufzeitprivilegien. Erstere ist sensible Personalfachhistorie, letztere technische und vom fachlichen Unternehmensexport ausgeschlossene Wiederholungsquittung. Beide wurden nach den isolierten Fach-/Replaytests durch die Integration registriert.
