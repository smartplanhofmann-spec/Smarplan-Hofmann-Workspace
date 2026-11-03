# Belegte Lohnzahlungen und EÜR: Schnittstellenvertrag

Stand 03.11.2026. Implementierter additiver Vertrag. Backend-Fallumfang,
Prüfergebnisse und Grenzen stehen in [CRM_ERP_LOHNZAHLUNGEN_EUER.md](CRM_ERP_LOHNZAHLUNGEN_EUER.md).

Es werden ausschließlich tatsächliche Zahlungen des unterstützten Lohnfalls
2026 übernommen. Berechnung, Bruttobetrag, Fälligkeit oder eine geänderte
Abrechnung erzeugen keine Geldbewegung. Die bereits vorhandenen Lohnkontobelege
enthalten tatsächliche Nettozahlungsteile. Abführungen benötigen zusätzlich einen
eigenen ausdrücklich bestätigten privaten Originalnachweis.

## Private Übernahme

Basis: `/business/payroll/cash`. Lesen erfordert aktuelle `personnel.read`,
`accounting.read` und `finance.read`. Schreiben zusätzlich `personnel.approve`,
`accounting.prepare` und `finance.write`, aktive Lohn-/Personal-/Finanzmodule,
installierte Brücke mit Feature `payroll_actual_cash`, freigegebene Finanzdaten
und feste Operator-Instanzbindung. Die Rechte
werden vor jeder Wiederholung erneut geprüft.

`GET /` liefert `instance_id`, `writes_allowed`, `batches` (Metadaten mit
`public_source`), `categories` und `limits`. `GET /batches/{id}` liefert zusätzlich
den ursprünglichen privaten `command`, `private_hash`, `source_records` und die
vorhandenen Nachweise. `source_records` enthält je Quelle `record`, `month`,
`calculation`, `scope_key`, `source_file`; die private Beschäftigtenkennung steht
unter `record.employee_id`. Eine optionale `revision` liest eine unveränderte Fassung.

`GET /sources?employee_id=…` liefert:

- `employee_id`, `instance_id`;
- `net_sources`: `id`, `revision`, `content_hash`, `kind` (`payment`/`carryover`),
  `month`, `source_file`, `eligible`, `issues`, `payments`;
- jedes Zahlungsteil: `index`, `paid_on`, `amount_minor` (vorzeichenbehaftete
  ganze Cent), `payment_reference`, `already_imported`, `import_batch_id`;
- `remittance_sources`: `source_kind` (`run`/`carryover`), `id`, `revision`,
  `content_hash`, `month`, `calculated`, `remaining`, `eligible`, `issues`;
- `evidence_files`: private Personaloriginale mit `id`, `employee_id`,
  `filename`, `media_type`, `sha256`, `content_hash` und `source_path`.

`POST /preview` erwartet exakt:

```json
{
  "batch_id": "32stelligeClientUUID",
  "expected_revision": 0,
  "instance_id": "gebundeneInstanzUUID",
  "action": "adopt",
  "kind": "net",
  "account_id": "GeldkontoUUID",
  "account_revision": 1,
  "sources": [],
  "settlement": null,
  "correction_file_id": null,
  "reason": "Ausdrücklicher Übernahmegrund"
}
```

`batch_id` wird vor der Vorschau erzeugt und bleibt bei Wiederholungen erhalten.
`action` ist `adopt` bei neuer Übernahme, `replace` bei belegter Nachweiskorrektur
oder `void` beim belegten Zurücknehmen einer fälschlich erfassten Zahlung.
Korrekturen verwenden dieselbe Batch-ID und ihre aktuelle `expected_revision`.
Sie benötigen `correction_file_id` eines geschützten Personaloriginals.
Bei `void` sind `sources: []` und `settlement: null` erforderlich; das ist keine
tatsächliche Rückzahlung. Tatsächliche Arbeitnehmer-Rückzahlungen sind negative
neue Nettozahlungsteile aus dem Lohnkonto.

Für `kind: net` enthält `sources` Einträge mit genau
`account_record_id`, `revision`, `content_hash`, `payment_indexes`.
Ausgewählte Teile müssen im vollständigen aktuellen Lohnkontobeleg nachgewiesen
sein. Bereits übernommene unveränderte Teile werden nicht ein zweites Mal bezahlt
oder gebucht; zusätzliche neue Teile können separat ausgewählt werden.

Für `kind: remittance` enthält `sources` Einträge mit genau
`source_kind`, `id`, `revision`, `content_hash`, `amounts`. `amounts` enthält
genau diese fünf nichtnegativen Centbeträge:

```json
{
  "employee_tax": 0,
  "employee_social": 0,
  "employer_social": 0,
  "employer_levies": 0,
  "employer_flat_tax": 0
}
```

Mindestens ein Betrag muss positiv sein. Die Beträge sind ausdrücklich
nachgewiesene Zahlungen, keine clientseitig automatisch übernommenen
Berechnungswerte. Die Vorschau gleicht sie gegen die gebundenen vollständigen
Lauf-/Vortragsquellen und bereits übernommenen Teile ab. `settlement` enthält
genau `paid_on`, `payment_reference`, `amount_minor`, `source_file_id`,
`employee_id`, `sha256`. Der Betrag muss der Summe der ausdrücklich ausgewählten
Abführungsanteile entsprechen; das private Original gehört zu einem der
betroffenen Beschäftigten. Fremde Dokumente sind keine Zahlungsquelle.

Die Vorschau liefert `batch_id`, neue `revision`, `kind`, `instance_id`,
`public_source`, `private_source_count`, `private_hash`, `preview_hash` und `warnings`.
`POST /batches` übernimmt genau denselben Vorschauauftrag zusätzlich mit
`request_id`, `preview_hash`, `confirmation: true`. Die Antwort enthält exakt
`id`, `revision`, `kind`, `status`, `instance_id`, `public_source`, `private_hash`,
`created_by`, `created_at`. Dieselben Metadaten stehen in der Batch-Liste.
Die Antwort enthält keine neu erfundene Bankbestätigung.

Bei verlorener Antwort bleiben Originalbody, Batch-ID und Vorgangs-ID erhalten.
Nur ausdrücklich `409 request_resolution: not_accepted` erlaubt das Verwerfen
des ausstehenden Auftrags. Rollen-/Instanz-/Vorgangs-ID-Konflikte tragen diesen
Marker nicht. Nachweiskorrekturen überschreiben keine alte Übernahme oder EÜR.

`writes_allowed` beschreibt die aktuellen Rollen-/Modul-/Restorebedingungen,
keinen historischen Annahmestatus. Ein bereits angenommener Auftrag bleibt nach
späterem Rechteentzug oder während einer Restore-Sperre ausstehend, bis seine
Quittung wieder unter gültigen Bedingungen gelesen werden kann.

Originaldateien bleiben im vorhandenen geschützten Personaldatei-Download
`/business/personnel/files/{id}/content`. Die
öffentliche Finanzprojektion hat keinen Zugriff auf diese Dateien.

## Öffentliche Finanzprojektion und EÜR

`GET /financial/{id}?revision=…` liefert einen unveränderlichen
`kind: payroll_cash`-Quellensnapshot mit `id`, `revision`, `instance_id`, `status`,
`date`, `cash_movements`, `proof_hash`, `source_path`, `source_hash`. `proof_hash`
bindet den privaten Nachweis als opaken SHA-256-Wert. Bewegungen enthalten
`id`, `date`, `account`, `direction`, `amount` und `categories`. Die Aggregation
erfolgt innerhalb des Batches je Geldkonto/Zahltag/Richtung, ohne Mitarbeiter-ID,
Name, Steuer-ID, rohe Zahlungsreferenz oder privaten Originaldateiverweis.

Die Kategoriebezeichnungen sind `payroll_net`, `payroll_employee_tax`,
`payroll_employee_social`, `payroll_employer_social`, `payroll_employer_levies`
und `payroll_employer_flat_tax`. Beträge in der öffentlichen Projektion sind
kanonische positive EUR-Zeichenketten; die Geldrichtung bestimmt ihr Vorzeichen.
`categories` ist eine Zuordnung Kategorie → EUR-Zeichenkette.

Die vorhandene EÜR-Vorschau/-Bestätigung erhält die neue Operation `payroll_cash`:

```json
{
  "batch_id": "BatchUUID",
  "revision": 1,
  "source_hash": "SHA256",
  "accounts": {"payroll_net": "6020"}
}
```

`accounts` enthält genau die tatsächlich vorhandenen Kategorien mit ausdrücklich
geprüften vierstelligen SKR04-Konten. Kein Konto wird aus personenbezogenen
Merkmalen abgeleitet. Zahlungstag und Betrag stammen unverändert aus der Quelle;
es entsteht keine Umsatzsteuer/Vorsteuer. Der bestehende EÜR-Journalstand,
Vorschauhash und Pendingmechanismus bleiben maßgeblich. Die Operation unterstützt
die bestehenden ausdrücklichen EÜR-Vorgänge `reverse` und `correct`.

Die allgemeine EÜR-Lese-/Schreibprüfung verlangt für diese öffentliche Quelle
keine Personalrechte. Private Übernahme und Nachweiskorrektur bleiben separat
geschützt. Ein geänderter Cash-Batch erfordert die ausdrückliche Berichtigung
seiner bestehenden EÜR-Einordnung; historische Exporte bleiben unverändert.

Jahreswechsel, steuerfreie Zusatzbezüge, Reiseauslagen, Unfallversicherung,
Krankenkassen-/Behörden-Erstattungen und nicht unterstützte Lohnsonderfälle werden
hier nicht aus Berechnungen abgeleitet. Der aktuelle Quellenfall beschränkt sich
auf tatsächliche Zahlungen im Jahr 2026. Keine Banküberweisung, amtliche Meldung
oder externe Abnahme wird ausgeführt oder behauptet.
