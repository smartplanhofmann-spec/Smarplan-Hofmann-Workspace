# Source5: begrenzte positive Netto-Korrektur

Additiver implementierter Vertrag, 09.11.2026. Basis af98278.
Der abschließende Integrationsnachweis steht am Ende dieser Datei.

Dies ist keine allgemeine Freigabe späterer Netto-/Steuererstattungen. Unterstützt
werden ausschließlich tatsächlich zusätzlich belegte positive Transfers am
unveränderten ursprünglichen Zuflusstag desselben einzelnen Bruttoereignisses.
Die Datumsgrenze ist die Grenze dieses Vertrags, keine aus dem alten Code
abgeleitete allgemeine steuerliche Behauptung.

## Unveränderliche Grenze

Laufender Originalfall und laufende Berechnung, Mitarbeiter, Arbeitgeber, Monat,
Komponenten-/Ereigniskennung, Brutto und Zuflusstag bleiben identisch. Die
korrigierte vollständige Rechnung beruht auf expliziten neuen Quellen. Ihre
Auszahlungsnettoschuld ist größer als die zuletzt tatsächlich erfüllte Schuld.
Alle früheren Zahlungsteile und Zuordnungen bleiben als exakter geordneter
Präfix erhalten. Frühere tatsächliche Abführungen dürfen in keiner Komponente
die korrigierte Gesamtschuld übersteigen. Ungeklärte oder korrigierte
Abführungsbelegketten bleiben gesperrt. Alte v1-Rechner und Belege bleiben
unverändert.

## Run-Übergang

Nur für diesen neuen Zweig erhält Vorschau und angenommener Lauf zusätzlich
`settlement_transition`. Der Vorschauhash bindet dieses Objekt neben `source`
und `calculation`. Der Rechen-/Quellenvertrag bleibt Source5/v7 unverändert.
Im neuen Zweig gehört zusätzlich zum Source5-Input das explizit bestätigte
`settlement_review` mit genau `schema_version:1`, `payments_complete:true`,
`remittances_complete:true` und `evidence_ref:{id,revision:1,content_hash}`.
Es muss eine konkrete unveränderte private Personaldatei derselben Person
bezeichnen. Beide Bestätigungen dürfen nicht vorbelegt werden. Erfasste Cash-
Batches allein beweisen keine vollständige Erfassung externer Abführungen.
Das Review wird in `source.input`, Transition und Annahmevorschau gebunden.
Der alte v1-Zweig erhält keines dieser zusätzlichen Felder.

Die Form des Übergangsobjekts lautet exakt:

```json
{
  "schema_version": 1,
  "contract": "source5_positive_net_correction_v1",
  "employee_id": "<32 hex>",
  "month": "2026-10",
  "previous_run_ref": {"id":"<32 hex>","revision":2,"content_hash":"<64 hex>"},
  "prior_run_ref": {"id":"<32 hex>","revision":2,"content_hash":"<64 hex>"},
  "prior_payment_ref": {"id":"<32 hex>","revision":1,"content_hash":"<64 hex>"},
  "prior_plan_hash": "<64 hex>",
  "old_composition_hash": "<64 hex>",
  "new_composition_hash": "<64 hex>",
  "component_key": "<32 hex>",
  "event_key": "<32 hex>",
  "receipt_date": "2026-10-31",
  "running_net_minor": 120000,
  "prior_total_net_minor": 159125,
  "total_net_minor": 160125,
  "additional_net_minor": 1000,
  "settlement_review": {"schema_version":1,"payments_complete":true,"remittances_complete":true,"evidence_ref":{"id":"<32 hex>","revision":1,"content_hash":"<64 hex>"}},
  "remittance_observation": {
    "schema_version":1,
    "head_sequence":0,
    "entries":[],
    "amounts":{"employee_tax":0,"employee_social":0,"employer_social":0,"employer_levies":0,"employer_flat_tax":0},
    "source_hash":"<64 hex>"
  },
  "transition_hash":"<64 hex>"
}
```

`transition_hash` ist SHA256 des kanonischen Objekts ohne dieses Hashfeld.
`remittance_observation.source_hash` ist entsprechend der Hash des
Beobachtungsobjekts ohne `source_hash`. `entries` enthält die für Person/Monat
relevanten ursprünglichen Abführungsbatches als
`{id, revision, sequence, private_hash}`. Das globale `head_sequence` bindet die
vollständige historische Sicht; spätere Batches ändern alte Übergänge nicht.
`previous_run_ref` bezeichnet die unmittelbar vorherige Laufrevision,
`prior_run_ref` die letzte wirklich bezahlte. Unbezahlte Zwischenrevisionen
dürfen die vorherige Zahlung nicht verdecken.

## Zahlungsversion2

Der engste Zweig erlaubt als vorherige Zahlung nur deren ursprüngliche
`revision:1`; berichtigte Vorzahlungsbelege benötigen ihre eigene Auflösung.
Die Eingabe der Lohnkonto-Zahlung behält alle bisherigen Zahlungsfelder und
verlangt `payment_source_schema_version: 2`, `prior_payment_ref` und die gesamte
Liste `payments` / `settlement_allocations`. `prior_payment_ref` muss zur
Run-Übergangsbindung passen. Alte Zahlungen und deren Zuordnungen werden exakt
kopiert; neue Anteile enthalten ausschließlich Bonusnetto für dasselbe Ereignis.

Das Ergebnis `sources.single_payment_plan` enthält genau die bisherigen
v1-Planfelder, mit `schema_version: 2` und
`contract: "source5_positive_net_correction_v2"`, sowie folgende zusätzliche Felder:

```json
{
  "prior_total_net_minor":159125,
  "additional_net_minor":1000,
  "prior_plan_hash":"<64 hex>",
  "transition_hash":"<64 hex>"
}
```

Die weiterhin vorhandenen Felder sind `employee_id`, `month`,
`composition_hash`, `event_key`, `bonus_receipt_date`, `running_net_minor`,
`one_off_net_minor`, `total_net_minor`, `payments`, `allocations`,
`prior_settlement_refs`, `preserved_prior_payment_indexes`,
`new_payment_indexes`, `actual_payment_created`, `cash_import_created`,
`claim_consumption_created` und `plan_hash`.
`prior_settlement_refs` bindet den alten Source5-Lauf und seine tatsächliche
Zahlung. Alle drei Nebenwirkungsflags bleiben `false`. `plan_hash` ist der Hash
aller Planfelder außer sich selbst.

Beispiel: unverändert 120000 laufendes Netto, früher 39125 Bonusnetto,
korrigiert 40125 Bonusnetto. Die ersten zwei alten Transfers bleiben identisch;
ein dritter echter Transfer über 1000 Cent am ursprünglichen Bonusdatum wird
hinzugefügt. Nur dessen neuer Index wird in einen neuen Cash-Batch übernommen.
EÜR bucht den zusätzlichen realen Abfluss von 10 EUR; die alten Batches und
Buchungen werden nicht ersetzt. Steigt eine früher tatsächlich abgeführte
Komponente über ihre korrigierte Schuld, wird dieser gesamte positive Zweig
verweigert.

## Offene Fachzweige

Geändertes Brutto, anderes Ereignis oder Zuflussdatum, Netto-Rückforderung,
Verrechnung, bereits überzahlte Steuer/SV und spätere Netto-/Steuererstattung
benötigen eigene explizite Verträge und Fachnachweise. Mehrere Steuergruppen
werden hier nicht freigegeben. Es findet keine tatsächliche Überweisung oder
Meldung statt.

## Backend-Kandidat und lokale Nachweise

Die Fachgrenze ist implementiert. Die tatsächliche Referenzkette korrigiert
zwei getrennte frühere Arbeitgeberbescheinigungen, ohne laufenden Oktoberfall,
Brutto, Anspruch oder Zuflusstag zu ändern. 2.000.000→1.000.000 Cent belegtes
Vorarbeitgeberentgelt ergibt mit unverändertem laufendem Netto 113332 Cent
Gesamtnetto 142457→146357 Cent, mithin 3900 Cent zusätzlich. Ein zweiter Ablauf
2.000.000→1.500.000→1.000.000 ergibt zusätzliche 1000 und 2900 Cent und erhält
sämtliche alten Zahlungsteile. Dies sind kontrollierte Referenzdaten, keine
zugesicherte Berechnung beliebiger Korrekturfälle.

Neun neue Fach-/Original-/Zahlungsfälle, neun gesonderte Abführungsbeobachtungen,
zwölf vorhandene v1-/Source5-/Jahres-/PDF-Regressionsfälle und 16 Paketfälle sind
lokal erfolgreich geprüft. Die neun neuen Fälle bestehen über gezielte Läufe
(fünf und drei Fälle mit einer Wiederholung, anschließend zwei zusätzliche
Fälle für ersetztes Vollständigkeitsoriginal und unbezahlte Zwischenrevision). Die vorherigen fehlerhaften
Testaufbauten bleiben dokumentiert: zuerst ungeeignete zukünftige
Beschäftigungsfakten, danach ein nicht positiver Betrag im ausgewählten
Steuerbereich. Keine Produktionsregel wurde dafür gelockert.

Neue Eingabefelder werden nur mit Feature `payroll_source5_positive_corrections`
angeboten, deklariert in `business_payroll.FEATURES`. Die alte Source5- und
v1-Hashbasis bleibt ohne neue Felder unverändert. Eine später versuchte
Revision eines durch diese Korrektur bereits gebundenen vorherigen
Zahlungsbelegs ist gesperrt; sie benötigt einen eigenen Ausgleichsvertrag.

Die beiden Clientintegrationen, tatsächliche PostgreSQL-/HTTP-/Restoreprüfungen
und eine eventuelle Veröffentlichung erfolgen im getrennten gemeinsamen
Integrationsstand. Dieser Backend-Kandidat allein ist keine Auslieferung oder
Fachfreigabe. Die 32 bisherigen 2026-Rechenmodule sowie das gesamte alte
`payroll_multiple_payments.py` sind gegen af98278 bytegleich.

Eine unbezahlte positive Zwischenrevision ist ausdrücklich geprüft: bezahlt
142457 Cent, unbezahlte Berechnung 146357 Cent, danach neue Berechnung 143457
Cent. Deren Berechnungsdelta ist -2900 Cent; die zusätzlich tatsächlich zu
belegende Zahlung ist trotzdem +1000 Cent gegen die alte wirkliche Zahlung.
Ein nach Laufannahme ersetzter Vollständigkeitsbeleg sperrt neue Zahlungen;
der ursprüngliche angenommene Lauf bleibt unverändert wiederholbar.
Die beiden Vollständigkeitserklärungen beziehen sich auf alle tatsächlichen
Vorgänge einschließlich externer Vorgänge, die im Programm vollständig belegt
sein müssen. Ein leeres Cash-Journal allein beweist ausdrücklich nicht deren
Nichtvorhandensein.


## Gemeinsame Integration am 09.11.2026

Backend, Browser und native App sind im gemeinsamen Integrationsbranch
zusammengeführt. Beide Clients zeigen frühere Zahlungsteile unveränderlich,
verlangen neue Vollständigkeitsbestätigungen und erhalten bei verlorener
Annahmeantwort den exakt ursprünglichen Auftrag. Schließen, Konto-/Personen-
wechsel und Rechteverlust öffnen keine privaten alten Dialoge erneut.

Die echten Fixtures verwenden eine dokumentiert korrigierte Vorarbeitgeber-
Bescheinigung bei unverändertem Bruttoereignis. Die Browser-/App-Fixture prüft
zwei positive Korrekturen (+10,00 EUR und anschließend +29,00 EUR), unveränderte
alte Zahlungsteile und genau einen Bonus von 500,00 EUR in der Jahresbasis.
Eine unbezahlte Zwischenrevision ist separat geprüft; die Nachzahlung bemisst
sich an der letzten tatsächlichen Zahlung und nicht am letzten Rechen-Delta.

Vier tatsächliche PostgreSQL-Fälle prüfen ursprüngliches CRLF-Original,
MFA/private Dateien, Zahlung/Cash/EÜR, Abführungsblockade, konkurrierenden
Abführungs-/Korrekturabschluss und konkurrierende Laufabschlüsse. Alle bestehen.
Der zusätzliche finale Fall prüft die Jahresbasis und eigene Mitarbeiter-
Datengrenzen vor und nach echtem Dump/Restore; ebenfalls bestanden.

Zwei echte Browserdurchläufe, 902 Browsermodulfälle, 23 ausgewählte Appfälle,
Appanalyse ohne Befund und 16 Paketprüfungen bestehen. Der umfassende Lohn-/
Reisesammellauf wird gesondert dokumentiert. Das beschleunigte Prüfen historischer
Originale wählt bekannte Metadatenvarianten vor und behält die vollständige
Gleichheitsprüfung; ein Vergleich mit der bisherigen vollständigen Variantensuche
besteht. Alle 32 Rechenmodule und die komplette alte v1-Zahlungsdatei sind
bytegleich zur Basis af98278.

[Rohprotokolle und Prüfsummen](evidence/source5-positive-correction-2026-11-09/integration-raw-logs.json).
Veröffentlichung, neue Remote-CI, Serverinstallation und tatsächliche Geräte-
bedienung sind getrennte Nachweise. Dieser Vertrag schließt weder mehrere
Steuergruppen noch negative oder anders datierte Nachzahlungen ab.
