# Private Jahresquellen für Einmalbezüge

Stand: 03.11.2026. Implementierter, global registrierter P5-Quellenvertrag.
Schema, API und Exportkatalog sind registriert. Eine bestätigte Jahresquelle
ist weder ein fertig gerechneter Einmalbezug noch eine Auszahlung. Die
Zusammenführung mit Lohnlauf v6, Lohnkonto, Cash/EÜR und Clients steht aus.
Gespeicherte Lohnregeln v1–v5 bleiben unverändert.

## Registrierung und Zugriffsgrenze

- Modul: `business_payroll_annual_basis`, reine Projektion:
  `payroll_annual_basis_2026`, Regel `de_2025_2026_annual_basis_v1`.
- Tabellen: `business_payroll_annual_events`,
  `business_payroll_annual_requests`. Nur SELECT/INSERT für die Laufzeitrolle;
  unveränderliche Datenbank-Guards auch gegen UPDATE/DELETE/REPLACE.
- Feature: `payroll_annual_basis`. Schreibsperre folgt dem Personal-/Lohnmodul.
- Alle Rohdaten benötigen aktuelle globale `personnel.read`-Berechtigung,
  Bestätigungen zusätzlich `personnel.approve`. Keine Personal-Selbstansicht
  für diese privaten Jahres-/Steuerquellen.
- Neue Nutzung verlangt aktuelle Quellenrevisionen. Angenommene Wiederholung
  prüft frische Rechte und liefert den exakten angenommenen Originalzustand,
  auch nach Stammdatenänderung oder Modulpausierung.

| Relativer Business-Pfad | Methode / Inhalt |
|---|---|
| `/payroll/annual-facts` | GET mit `employee_id`, optional `kind`; POST Bestätigung/Korrektur |
| `/payroll/annual-facts/preview` | POST konkrete Quellenprüfung und Vorschau |
| `/payroll/annual-facts/sources` | GET mit `employee_id`; private P2-Quellen, `annual_facts`, tatsächliche `payroll_runs`, `payroll_payments`, `calculation_cases` |
| `/payroll/annual-facts/{id}` | GET aktuelle Fassung |
| `/payroll/annual-facts/{id}/history` | GET alle unveränderlichen Fassungen |

POST-Queryparameter, zusätzliche Objektschlüssel, GET-Bodies und falsche
Methoden werden abgelehnt. Globale Registrierung muss beide Tabellen auch in
Paket, Export/Restore und Laufzeitprivilegien vollständig aufnehmen.

## Gemeinsamer Auftrag und unveränderliche Referenzen

Eine Referenz `ref` besitzt genau `id` (32 Hexzeichen), `revision` (positive
ganze Zahl) und `content_hash` (64 Hexzeichen). Originaldateien verwenden ihre
tatsächliche Datei-ID, Revision 1 und gespeicherten Inhaltshash. Jede in den
Details genannte Originalreferenz muss über `source_file_ids` als geschützte
Personaldatei derselben Person auflösbar sein. Die Referenz belegt Existenz und
Unverändertheit. Die fachliche Inhaltsprüfung externer Abrechnungen erfolgt
ausdrücklich durch die bestätigende Person.

Vorschau enthält genau:

```text
employee_id, employee_revision, kind, details, source_file_ids[]
```

Bestätigung ergänzt genau:

```text
request_id, revision, status, confirmed, preview_hash
optional: id, correction_reason
```

`revision=0` erzeugt einen neuen Fakt; Korrektur bindet `id`, letzte Revision
und begründeten `correction_reason`. `status` ist `active` oder `void`.
Archivierung übernimmt die unveränderten Details, Dateien und Vorschau der
aktiven Fassung. `confirmed` muss ausdrücklich wahr sein. Neue Verwendung
eines archivierten oder korrigierten Originals ist gesperrt. Die ursprüngliche
Fallidentität bleibt bei Korrekturen erhalten.

Alle `details` enthalten `employer_identity_ref` und `verification_note`.
Arbeitgeberidentität stammt aus einem echten Lohnkonto-Identitätsnachweis und
wird gegen dessen tatsächliches Profil rekonstruiert. Person und Arbeitgeber
werden nicht aus freiem Clienttext für interne Lohnperioden übernommen.

Antworten enthalten Details, konkrete `sources`, den hergeleiteten `plan`,
Vorschau-/Quellen-/Inhaltshashes und Historienmetadaten. Der vollständige
angenommene Befehl bleibt ausschließlich privat im gespeicherten Ereignis.
Restore prüft ihn gegen die Annahmequittung, Originalquellen, Personenfassung
und erneut hergeleiteten Plan. Neu berechnete Hüllenhashes allein reichen nicht.

## `imported_period`: konkrete externe Lohnperiode

Zusätzliche Details:

```text
period_start, period_end, employment_from, employment_to|null
section_key: regular|minijob
profile: {
  scheme: regular_standard|regular_transition|commercial_minijob,
  health_insurance: statutory_mandatory|statutory_voluntary|private,
  health_additional_percent, saxony, childless_surcharge,
  care_child_discounts, minijob_rv_exempt, pension_other_compulsory,
  u1_percent, u2_percent
}
branches: {health, care, pension, unemployment: {
  eligible_intervals: [{start, end, legal_reason, evidence_ref}],
  total_minor, employee_minor
}}
running_gross_minor, running_taxable_minor
running_receipts: [{received_on, taxable_minor, evidence_ref}]
original_rule_version, original_rule_hash, original_payroll_reference
document_refs[]
```

Die Periode liegt vollständig in einem Monat 2025 oder 2026. Beitragsintervalle
liegen innerhalb der tatsächlichen Beschäftigung und überschneiden sich nicht.
`legal_reason` ist `paid_employment`, `continued_section_7_3`,
`contributory_section_23c` oder `short_time_contributory`. Branchen ohne
Beitragspflicht haben weder künstliche SV-Tage noch eine Beitragsbasis.
`total_minor` ist die bereits verbeitragte Basis, nicht das oberhalb der BBG
liegende Brutto. Teil-BBG und AN-/Gesamtbasis werden geprüft. Der tatsächliche
historische Zusatzbeitrag ist erforderlich; ein Durchschnittswert ersetzt ihn
nicht. Die externe ursprüngliche Steuerrechnung wird nicht als neu geprüfte
PAP-Rechnung ausgegeben.

Zuflussdaten dürfen bei neuer Erfassung nicht in der Zukunft liegen. Fehlende
Zuflüsse sperren die darauf aufbauende Steuerprognose. Laufender Vorjahreslohn
bis 21. Januar bleibt im ursprünglichen Steuerjahr; spätere Vorjahresnachzahlung
braucht ihren eigenen steuerlichen Zuordnungsfall. Sie wird nicht automatisch
zum SV-Einmalbezug. Quellen: LStR 2026 R 39b.2 und R 39b.5.

## `imported_one_off`: bereits verarbeiteter tatsächlicher Einmalbezug

```text
receipt_date, amount_minor, assigned_period_ref, section_key
bases_minor: {health, care, pension, unemployment}
original_reference, document_refs[]
```

`assigned_period_ref` bindet eine echte `imported_period`-Fassung desselben
Arbeitgebers und Abschnitts. Der Plan hält Steuerjahr des Zuflusses und
SV-Jahr der Zuordnung getrennt. Die Branchenbasen dürfen den Bezug nicht
überschreiten. Dies ist eine geprüfte externe Originalzuordnung, keine freie
Eingabe fertiger jährlicher SV-Luft. Interne zukünftige v6-Einmalbezüge brauchen
zusätzlich ihren eigenen kanonischen Lauf-/Verbrauchsnachweis.

## `annual_basis`: lückenlose Jahresdeckung zu einem konkreten Stichtag

```text
year: 2025|2026, coverage_to, as_of_date
payroll_run_refs[], payroll_payment_refs[]
imported_period_refs[], imported_one_off_refs[]
current_calculation_case_ref|null
gaps: [{start, end, reason: not_employed|contribution_free_interruption,
        evidence_ref}]
completeness_confirmed: true
```

`coverage_to` begrenzt die tatsächlich zugeordneten SV-Perioden.
`as_of_date` ist der konkrete Beurteilungs-/Zuflussstichtag. So darf eine später
zugeflossene, rückwärts zugeordnete Bonuszahlung eine frühere SV-Luft nicht
verbrauchen. Die Fallidentität umfasst Jahr, Deckungsende und Stichtag.

Alle einschlägigen aktuellen internen Läufe, Importperioden und bereits
zugeflossenen Einmalbezüge sind verbindlich. Vom 1. Januar bis zum Deckungsende
muss jeder Kalendertag genau einmal durch Perioden oder ausdrücklich belegte
Lücken gedeckt sein. Leere Monate bedeuten keine Null. Interne und importierte
Perioden dürfen sich nicht doppeln.

Die optionale aktuelle Source3-Rechnung ersetzt ausschließlich den laufenden
letzten Monat. Ihr laufender Lohn wird ausdrücklich als geplant gekennzeichnet;
es entsteht keine fiktive Steuerbuchung oder Zahlung. Gespeicherte tatsächliche
Läufe werden mit ihrer ursprünglichen Regelversion, ihren Originalquellen und
bei v5 auch dem tatsächlichen atomaren Steuererfassungsnachweis geprüft.

`payroll_payment_refs` bindet exakte tatsächliche Lohnkonto-Zahlungsfassungen.
Ein später erfasster Zufluss macht eine neue Verwendung ohne diese Quelle
unvollständig, verändert aber keine historische Jahresfassung. Pauschal
besteuerte Minijobperioden erzeugen kein individuelles Jahressteuerbrutto.

Der Plan enthält getrennte Branchenintervalle, bereits verbrauchte Basen,
hergeleitete SV-Tage, Teil-BBG, Restluft und Quellenbindungen. Volle Monate
zählen mit 30 Tagen; Teilintervalle verwenden ihre tatsächlichen Tage. 2025
und 2026 verwenden ihre jeweils eigenen BBG.

## `one_off_earning`: konkreter noch geplanter Anspruch

```text
claim_key: ref, claim_reference
planned_receipt_date, amount_minor
tax_classification: other_payment
social_classification: one_off_remuneration
section_key: regular|minijob
employment_terms_refs[]
claim_periods: [{start, end, evidence_ref}], document_refs[]
```

`claim_key` ist das konkrete Anspruchsoriginal; `claim_reference` unterscheidet
nachgewiesene Positionen desselben Originals. Dieselbe Position darf nicht als
zweiter Anspruch neu erfasst werden. Alle Anspruchstage müssen durch wirkliche
Beschäftigungsnachweise gedeckt sein. Diese erste Form ist für echte sonstige
Bezüge und echtes einmaliges Arbeitsentgelt bestimmt. Laufende Nachzahlungen
oder auf verschiedene Versicherungsabschnitte aufzuteilende Ansprüche brauchen
ihre gesonderte belegte Klassifikation. Tatsächliche Zahlung und Übermittlung
werden ausdrücklich nicht behauptet.

## `annual_tax_forecast`: hergeleiteter Jahresarbeitslohn

```text
annual_basis_ref, receipt_date, identity_ref, current_one_off_ref
remaining_periods: [{month, employment_terms_ref, agreement_refs[],
                     work_schedule_ref|null}]
previous_employers: [{employer_name, employer_tax_number, start, end,
                     running_taxable_minor, other_paid_minor, evidence_ref}]
no_previous_employer_ref|null, other_tax_receipt_refs[]
```

Jahresbasis und aktueller Anspruch müssen genau zum Zuflussfall passen. Alle
verbleibenden Monate bis Dezember werden ausdrücklich mit echten Verträgen
und gegebenenfalls geplanten Sollzeiten belegt. Tatsächliche Projektzeiten
werden dabei nicht geschrieben. Jede einschlägige künftige Vertragsänderung
muss enthalten sein. Mehrere gleichzeitige zukünftige Beschäftigungsabschnitte
und Wechsel zwischen Pauschal-/Individualbesteuerung brauchen ihren eigenen
vollständigen Zuordnungszweig; sie werden nicht geraten.

Belegte frühere Arbeitgeber werden getrennt berücksichtigt; eigener Lohn,
doppelte und zeitlich überlappende Vorbezüge dürfen nicht nochmals eingehen.
Ohne Vorarbeitgeber ist ein konkreter ausdrücklicher Originalnachweis nötig.
Eine gesetzliche Ersatzschätzung ohne Originalvorbezüge ist hier noch nicht
implementiert. Andere bereits enthaltene Zuflussreferenzen dürfen nicht
erneut angegeben werden.

Der erwartete Jahreslohn enthält laufende belegte Jahresbezüge, bereits
erhaltene sonstige Bezüge, Vorarbeitgeber und hergeleiteten restlichen laufenden
Lohn. Der aktuelle Einmalbezug bleibt ausgeschlossen. Jahresfreibetrag und
Jahreshinzurechnung stammen aus tatsächlichen gültigen ELStAM-/Finanzamts-
Nachweisen. Ein pauschaler Minijobnachweis ist dafür ungeeignet.

## Ausgeführte Prüfung und verbleibende Integration

15 private Domänenfälle und zwei reine Jahreswechselgrenzen bestanden im
aktuellen Quellenstand, darunter Source3-Vorschau → tatsächlicher Lauf →
späterer Zahlungsnachweis, unveränderte historische Wiederholung, tatsächliche
Vertragsprognose, fehlende Zuflüsse, Rechte, Tabellen-Guards und Manipulation.
Zwei echte lokale HTTP-Fälle bestanden. Der erste Sandboxversuch konnte keine
Sockets öffnen; der anschließend erlaubte Loopbacklauf war grün.

Vier unabhängige Gegenfälle sichern zusätzlich die getrennten Steuer-/SV-Jahre,
die tatsächliche 2025-BBG, spätere Originale und die 21.-Januar-Grenze. Die dabei
gefundene fehlende Vollständigkeitsprüfung für 2026 zugeflossene, der SV 2025
zugeordnete Bezüge ist behoben. Bekannte solche Originale müssen ausdrücklich
gebunden sein; historische angenommene Zustände bleiben unverändert.

Nach diesem Fix bestanden 56 Kern-/Domänen-/Gegentests, zwei echte lokale
HTTP-Fälle und drei PostgreSQL-Fälle. Der letzte PG-Lauf verlangte die echte
globale Registrierung genau einmal und ergänzte keine testlokale Registrierung.
Er prüfte MFA-/HTTP-Rechte, SQL-Laufzeitrechte, unveränderliche Tabellen,
parallele Annahme, additive Migration, reale Sicherung/Wiederherstellung,
Originaldateibytes und unveränderte Quittungen.

Ergebnis und Dateihashes: `docs/evidence/payroll-annual-integrated-2026-11-03.json`.
Finale Logs: `work/verification/payroll-oneoff-annual-domain-final.log`,
`work/verification/payroll-annual-http-final.log`,
`work/verification/payroll-annual-pg-global.log`. Frühere Versuche bleiben
erhalten. Echte synthetische Antwortverträge aller fünf Arten liegen unter
`docs/fixtures/payroll-annual-basis-2026.json`.

Diese Nachweise beschreiben den Stand vom 03.11.2026. Die spätere Source4/v6-Integration ist im folgenden Nachtrag getrennt dokumentiert.

## Nachtrag 04.11.2026: tatsächliche interne Source4-Jahresfolgen

Source4-Läufe sind nun zulässige interne Jahresoriginale. Die laufende Beitrags-/Steuerprojektion wird aus ihrer unveränderten v5-Teilrechnung hergeleitet; der tatsächliche Bonus wird gesondert mit Steuerjahr, SV-Jahr, Zuordnungsreferenz, Abschnittsschlüssel und branchengenauen Beitragsbasen gebunden. Der vollständig bestätigte tatsächliche Zahlungsnachweis muss bis zum Stichtag vorliegen. Bekannte Läufe oder Zahlungen dürfen nicht ausgelassen werden.

Neue Source4-Quellen speichern flache `source4_annual_reference_v1`-Lohnreferenzen und kompakte Zahlungsnachweise. `internal_periods` enthält zusätzlich `one_off_payment` und die genauen historischen `assignment_profiles`. Die Originale werden über ihre exakten Referenzen aus dem Archiv vollständig verifiziert; diese Felder sind keine freien Clientangaben. Vorhandene v1–v5-Quellen bleiben unverändert nachrechenbar.

Ein Anfang 2026 tatsächlich gezahlter, Ende 2025 zugeordneter Bonus vermindert allein die 2025-SV-Luft, erhöht aber die 2026-Steuerbasis. Ein außerhalb des laufenden Jahres gebundener Lauf liefert dafür keine falschen laufenden Kalendertage. Bei einer Korrektur desselben Anspruchs nimmt der private Resolver ausschließlich dessen zu ersetzenden eigenen Verbrauch aus; dies ist kein Clientfeld. Ein zweiter Märzklauselbonus muss dagegen den tatsächlichen früheren Bonus und dessen bereits verbrauchte 2025-Basis berücksichtigen. Drei echte aufeinanderfolgende synthetische Bonusmonate mit isolierter Testuhr sowie neu gehashte Manipulationen werden in `backend/test_business_payroll_oneoff_annual.py` geprüft. Nachweis: `docs/evidence/payroll-oneoff-annual-followup-2026-11-04.json`. Der aktuelle Gesamtvertrag steht in `CRM_ERP_LOHN_EINMALBEZUG_V6_VERTRAG_2026.md`.
