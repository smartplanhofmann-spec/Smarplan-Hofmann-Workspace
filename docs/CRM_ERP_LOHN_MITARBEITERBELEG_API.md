# Reduzierter Mitarbeiter-Lohnnachweis

Stand: 03.11.2026. Der lesende Adapter `business_payroll_statements.py` läuft
unter der vorhandenen Payroll-Fähigkeit. Das neue Feature heißt
`payroll_employee_statements`. Es gibt keine neue Tabelle, Migration,
Schreiboperation oder Änderung an den privaten Lohnquellen-Rechten.

## Autorisierung und Darstellung

Aktuelle globale `personnel.read` oder die aktuelle Zuordnung der eigenen
Mitarbeiter-ID zum angemeldeten Benutzer zusammen mit `time.own` erlauben das
Lesen. Der eigene reduzierte PDF-Beleg ist mit dieser eigenen Freigabe
herunterladbar. Für PDF-Belege fremder Mitarbeiter ist zusätzlich
`personnel.export` erforderlich. Der frische Mitarbeiterzugang wird vor dem
Quellenzugriff und nach der außerhalb des Datenbankschlosses ausgeführten
PDF-Erzeugung erneut geprüft. Modulpausierung sperrt keine historischen
Lesebelege. Vorhandene Offlinegrenzen gelten unverändert.

Der Browser und die native App wechseln am bisherigen Payroll-Einstieg für
eigene Nutzer ohne globale Personalrechte direkt zu **Meine Lohnnachweise**.
Dieser Pfad ruft keine privaten Payroll-Läufe, Profile oder Lohnfakten ab.
Personalverantwortliche erreichen dieselbe reduzierte Sicht über
**Mitarbeiter-Lohnnachweise ansehen**. Die Oberfläche zeigt neueste Fassungen,
Einzelbeleg, eigene PDF-Ausgabe und historische Fassungen.

## Lesende Routen

| Route unter `/business` | Query | Antwort |
|---|---|---|
| `/payroll/employee-statements` | `employee_id` optional, sonst eigene Zuordnung | `{employee_id,can_export,items:[statement]}`; nur letzte wirksame Fassung pro Lauf |
| `/payroll/employee-statements/{run_id}` | `revision` optional | `{employee_id,can_export,statement}` |
| `/payroll/employee-statements/{run_id}/history` | keine | `{employee_id,can_export,items:[statement]}`; aufsteigende Revisionen |
| `/payroll/employee-statements/{run_id}/pdf` | `revision` und `statement_hash` erforderlich | Der genau gebundene reduzierte PDF-Beleg |

Alle Routen erlauben ausschließlich GET. Zusätzliche Query- oder Bodyfelder,
falsche Fassungen und abweichende Belegprüfsummen werden zurückgewiesen.
`can_export` ist eine aktuelle Zugangsaussage im Wrapper und gehört nicht zum
unveränderlichen Beleg.

## Positiv freigegebener Beleg

`statement` enthält exakt:

- `schema_version: 1`, `employee_id`, historischer `employee_name`,
  `month`, historisches `created_at`;
- `run_ref: {id,revision,content_hash}` als Bindung an den internen Ursprung;
- `calculation`: `rule_version`, `scope`, `currency: EUR`,
  `payroll_calculation_complete`, `employee_contributions` mit den fünf
  Beitragszweigen sowie `gross_minor`, `employee_social_total_minor`,
  `individual_wage_tax_minor`, `solidarity_minor`, `church_tax_minor`,
  `employee_tax_minor`, `net_minor`, `payout_minor`,
  `employee_additional_payment_minor`, `employer_flat_tax_minor`;
- `period_summary: null` für historische Vollmonate oder ausschließlich
  `employment_intervals[{start,end,calendar_days}]`,
  `tax_periods[{start,end,lzz,tax_days}]` und
  `social_periods[{start,end,days,full_month}]`;
- `transmission_status: not_transmitted`,
  `payment_status: not_evidenced_by_calculation`;
- `statement_hash`, `pdf_sha256`, `pdf_size`.

Die Projektion kopiert auch verschachtelt nur ausdrücklich benannte Felder.
Keine Personaloriginale, Profilinhalte, Steueridentitäten, Originalreferenzen,
Vertragsgründe, Anspruchsentscheidungen oder Korrekturfreitexte werden übernommen.
Der historische Mitarbeitername stammt aus dem eingefrorenen HR-Snapshot.
Eine spätere Namensänderung verändert frühere Belege nicht.

`statement_hash` ist SHA-256 des kanonischen JSON-Belegs ohne die drei Hash-/
Größenfelder. JSON-Schlüssel werden rekursiv sortiert; UTF-8 und kompakte
Trennzeichen entsprechen der bestehenden Backend-Kanonisierung. Das
deterministische PDF wird ausschließlich aus dieser reduzierten Projektion
erzeugt. Es ist ein eigener Beleg mit eigener Prüfsumme, keine umbenannte
Kopie des internen Lohn-PDF. Browser und App prüfen Schema, Person, Fassung,
Summen, Belegprüfsumme und tatsächlich empfangene PDF-Bytes.

Vor der Projektion werden der interne gehashte Lohnumschlag und seine Rechnung
geprüft. Bei Quellen-v2 werden zusätzlich die unveränderten historischen
Faktenquellen und die exakte Periodenrechnung validiert. Die Berechnung bleibt
serverseitig. Die ursprünglichen Roh- und PDF-Routen behalten ihre bisherigen
Personalrechte.

## Umfang und Folgeversion

Der hier implementierte Stand deckt die vorhandenen v1–v4-Berechnungen ab,
einschließlich früherer unvollständiger SV-Berechnungen mit unbekanntem Netto.
Die v5-Segmentrechnung benötigt neue Scope-Bezeichnungen sowie eine getrennte
Abbildung von Nettoabzügen; ihre Integration erfolgt erst gegen den endgültigen
v5-Vertrag und echte Fixtures. Das Weglassen einer privaten Quelle bedeutet
keine amtliche Entgeltbescheinigung, keine Zahlung und keine Meldung.
