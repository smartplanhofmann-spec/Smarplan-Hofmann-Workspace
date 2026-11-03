# E1a: belegte EUR-Geldflüsse – Implementierungsvertrag

Stand: 02.11.2026, Basis `060246b`. Konkretisierung des
[EÜR-Plans](CRM_ERP_EUER_PLAN.md). Dieser Vertrag beschreibt die E1a-Implementierung;
ausgeführte Prüfungen stehen separat im [Fortschrittsbericht](CRM_ERP_FORTSCHRITT.md).
Er ersetzt keinen vollständigen EÜR- oder Abnahmenachweis.

## Umfang und Rechte

Neues additives Modul `business_accounting`, Feature `accounting_prejournal`.
E1a erfasst bestätigte Geldflüsse und deren unveränderliche Herkunft. Es
erzeugt keine Steuerberechnung, vollständige EÜR, Bankbestätigung, neue
Kundenzahlung oder Änderung bestehender offener Posten. Steuerstatus bleibt
`unconfigured`, Einordnung jedes Geldflusses `unclassified`.

Alle Routen liegen unter `/api/v1/business/accounting`. Sie verlangen global
`accounting.read` **und** global `finance.read`. Geldflüsse erfordern zusätzlich
global `accounting.prepare`, Kontenänderungen global `accounting.admin`.
Neue Rechte haben keine Mitarbeiter-Standardfreigaben. Projektbezogene
Accounting-Grants berechtigen nicht zu diesen Routen. Die bestehende
Fachrechteverwaltung weist neue projektbezogene Accounting-Grants ausdrücklich
ab; gespeicherte Fremd-/Altzeilen ersetzen keine globale Berechtigung. Die
bestehenden Finance-Quellrechte gelten zusätzlich, einschließlich Projektzuweisung und
Owner-/Erstellergrenze für projektlose Eingangsbelege/unzugeordnete Zahlungen.

Bei mehreren Rechnungszuordnungen muss die gesamte Zahlung lesbar sein.
Listen lassen nicht lesbare Quellen vollständig aus; keine fremden Teilbeträge,
Gesamtsummen oder `hidden_count`. Kennzeichnung: `scope:'authorized_sources'`
und „Nur freigegebene Quellen“. Das Vorjournal hat keinen Projektfilter und
behauptet keine vollständige Unternehmenssicht. Originaldownloads verwenden
weiterhin die vorhandenen berechtigten Finanz-/Dokumentrouten.

Alle Schreibvorgänge verlangen aktiven Businessmodus, aktiviertes bestehendes
Modul `finance` und abgeschlossenen Restore-/Finanzabgleich. PostgreSQL prüft
zusätzlich die bestehende getrennte Runtime-Rolle. SQLite ist für dieses
Vorjournal technisch unterstützt, ohne eine produktive steuerliche
Unveränderbarkeits-/Ausstellerfreigabe zu behaupten. Keine Sicherheitsausnahme
wie beim Portalwiderruf. Konstruktor/GET erzeugen keine Tabellen oder Buchungen.

## Routen

Alle IDs/Anfrage-IDs: 32 Hexzeichen. Hashes: 64 Hexzeichen. Unbekannte Felder,
zusätzliche Queryparameter, doppelte Filter und nicht unterstützte Methoden
werden abgewiesen. Geldbeträge sind positive kanonische EUR-Centstrings mit
genau zwei Nachkommastellen, höchstens `999999999.99`; keine Rundung von
Eingaben. Datumsfelder sind gültige ISO-Kalendertage `YYYY-MM-DD`.

| Methode/Pfad relativ zu `/accounting` | Eingabe | Antwort |
| --- | --- | --- |
| GET `/status` | keine | `{profile_status:'unconfigured',tax_status:'unconfigured',tax_result_available:false,scope:'authorized_sources',writes_allowed}` |
| GET `/accounts` | keine | `{items:[Account]}` einschließlich inaktiver Konten, nach Code/ID sortiert |
| POST `/accounts` | `request_id,code,name,kind,confirmation:true` | Account, 201 |
| POST `/accounts/{id}` | `request_id,revision,name,active,confirmation:true` | Account, 200 |
| GET `/sources/payments` | optionale `limit,offset` | `{items:[PaymentSource],total,next_offset,scope:'authorized_sources'}` |
| GET `/sources/receipts` | optionale `limit,offset` | `{items:[ReceiptSource],total,next_offset,scope:'authorized_sources'}` |
| GET `/events` | optionale `limit,offset` | `{items:[CashEvent],total,next_offset,scope:'authorized_sources',tax_result_available:false}` |
| GET `/events/{id}` | keine | CashEvent |
| POST `/events/import-payment` | `request_id,payment_id,source_hash,account_id,account_revision,cash_date,evidence_reference,confirmation:true` | CashEvent, 201 |
| POST `/events/payout` | `request_id,receipt_id,source_hash,review_revision,review_sha256,original_sha256,account_id,account_revision,expected_cash_revision,amount,cash_date,evidence_reference,reference,confirmation:true` | CashEvent, 201 |

Listen: `limit` standardmäßig 50, 1–100; `offset` standardmäßig 0,
0–100000. Sortierung der Quellen nach `created_at DESC,id`, Ereignisse nach
`sequence DESC,id`; `total` zählt ausschließlich aktuell sichtbare Einträge.
Seiten sind kein Nachweis einer effizienten Suche in sehr großen Beständen.

## Datenformen

Account: `{id,code,name,kind,currency:'EUR',active,revision,created_by,created_at}`.
`code` ist ein stabiler eindeutiger Code aus 1–40 Zeichen `[A-Za-z0-9_-]`,
case-insensitiv eindeutig; `name` 1–200 Zeichen. `kind` ist `bank`, `cash` oder
`payment_service`; Code, Art und Währung bleiben unveränderlich. Neue Konten
sind aktiv, Revision 1. Änderungen hängen eine neue Version an. Keine IBAN,
Anbieterkennwörter oder behauptete Bankanbindung in dieser ersten Kontenmaske.

PaymentSource: `{payment_id,kind,direction,amount,currency,booking_date,
reference,source_id,source_hash,allocations,unallocated,linked_event_id}`.
`kind` bewahrt `receipt|refund`; `direction` ist entsprechend `in|out`.
`allocations` enthält ausschließlich `{document_id,number,project_id,amount,
payload_sha256,pdf_sha256}`, deterministisch nach Dokument-ID sortiert.
`linked_event_id` ist null oder die bestehende Vorjournalreferenz.
`source_hash` bindet die ursprüngliche unveränderliche Zahlungszeile, alle
Zuordnungen und die finalen Dokument-/Archivhashes, keine dynamischen OP-Reste.

ReceiptSource: `{receipt_id,project_id,filename,media_type,original_sha256,
review_revision,review_sha256,source_hash,vendor,invoice_number,issue_date,
net,tax,gross,currency,cash_revision,paid_amount,remaining_amount,payable,
blocked_reason}`. Nur aktuell `reviewed` geprüfte EUR-Belege mit positivem
Brutto sind Kandidaten. `source_hash` bindet Originalmetadaten/-hash und die
konkrete unveränderliche Prüfversion. `cash_revision` zählt bereits bestätigte
E1a-Auszahlungen auf diesen Beleg; `paid_amount`/`remaining_amount` sind reine
Auszahlungsbeträge, keine Steuer- oder Kostenwerte. Eine geänderte Prüfversion
nach einer ersten Auszahlung sperrt in E1a weitere Auszahlungen mit
`blocked_reason:'review_changed'` bis zur späteren ausdrücklichen Klärung.
Ein unter anderer ID bereits zahlungsgebundenes identisches Original sperrt
mit `duplicate_original`, ohne fremde IDs/Beträge zu nennen. Vollständig
ausgezahlte Belege bleiben sichtbar (`payable:false,blocked_reason:'paid'`).
Bei möglicher Überzahlung nach neuer Prüfung wird `remaining_amount` als
`0.00` angezeigt, die neue Prüfung bleibt als Konflikt erkennbar.

CashEvent: `{id,sequence,account,direction,amount,currency,cash_date,
evidence_reference,reference,source,classification_status:'unclassified',
unresolved_reasons,created_by,created_at}`. `account` ist die bei Erfassung
bestätigte Accountversion. `sequence` ist eine eindeutige fortlaufende Nummer.
`source` ist `{kind:'payment'|'receipt',id,source_hash,snapshot}`.
Payment-Snapshot: dieselben PaymentSource-Felder ohne `linked_event_id` und
ohne `source_hash`; Receipt-Snapshot: dieselben ReceiptSource-Felder ohne
`source_hash,cash_revision,paid_amount,remaining_amount,payable,blocked_reason`.
Keine Originalbytes in Listen/Snapshots. Der gehasht gebundene interne
Quellennachweis darf zusätzliche stabile Daten für Integritätsprüfung enthalten;
sein kanonischer Aufbau wird im Modul mit Tests festgeschrieben.
`unresolved_reasons` enthält mindestens `tax_profile_unconfigured`; bei alten
Refunds außerdem `refund_origin_unresolved`. Es wird kein ursprünglicher
Erstattungsbezug erfunden. E1a bietet keine steuerlichen Summen oder Gewinne.

## Fachliche Schreibregeln und Wiederholungen

`evidence_reference` ist die ausdrücklich bestätigte, stabile Referenz des
Geldflusses auf dem ausgewählten Konto (1–200 Zeichen), `reference` ein
Verwendungszweck (0–1000 Zeichen). Beide enthalten keine Steuerklassifikation.
Eine Konto-/Nachweisreferenz ist über beide Erfassungswege eindeutig. Datum,
Betrag und Freitext allein werden nicht als Dublettenschlüssel verwendet.
Für den Eindeutigkeitsvergleich wird die Nachweisreferenz mit Unicode-NFKC,
`casefold` und auf ein Leerzeichen reduzierten Leerraumfolgen normalisiert.
Die Anzeige erhält die getrimmte Originalschreibweise.

Eine vorhandene `payment_id` kann unabhängig von Benutzer, Konto und Request-ID
höchstens einmal übernommen werden. Betrag, Richtung, ursprüngliches
Buchungsdatum, Referenz und Rechnungszuordnungen stammen aus der geprüften
Quelle; `cash_date` und Konto werden ausdrücklich bestätigt. Es wird weder
`Finance.record_payment` aufgerufen noch eine bestehende Zahlung geändert.
Ein anderer erneuter Übernahmeversuch liefert 409 mit Hinweis auf Prüfung des
vorhandenen Stands, ohne eine zweite Geldbewegung anzulegen.

Eine manuelle Auszahlung ist ein neuer bestätigter Geldabfluss, keine
Überweisung. Sie bindet aktive Accountrevision, aktuellen Originalhash,
aktuellste Prüfversion/-hash und erwartete `cash_revision`. Alle Auszahlungen
auf dieselbe Quelle werden konten-/benutzerübergreifend atomar summiert; die
Summe darf deren eingefrorenes Brutto nicht überschreiten. Ein identisches
Original unter einer zweiten Beleg-ID eröffnet keinen zweiten Zahlungsrahmen:
bei bereits vorhandener anderer Quellenbindung wird der neue Versuch mit
409 zur Klärung abgewiesen. Kein automatisches Zusammenführen fremder Belege.

Vor jeder Wiederholungsantwort gelten frische Accounting- und Quellrechte,
unveränderte historische Original-/Quellenbindung sowie Modul-/Restoregate.
Gleiche Anfrage-ID und gleicher vollständiger Inhalt liefern denselben
eingefrorenen CashEvent. Geänderter Inhalt ergibt 409. Erst bei einem wirklich
neuen Vorgang werden aktuelle Accountaktivität/-revision, Latest-Review und
Restbetrag geprüft. Eine spätere legitime Belegprüfung oder Kontenumbenennung
ändert weder den alten CashEvent noch dessen erfolgreiche Wiederholung.

Alte Quellensätze bleiben unverändert. Neue append-only Tabellen erhalten
Runtime-ACLs und SQLite-REPLACE-Schutz für alle Schlüssel. Das neue Modul
ergänzt außerdem additive SQLite-BEFORE-INSERT-Konfliktguards an den alten
Tabellen `business_payments`, `business_payment_allocations`,
`business_incoming_receipts` und `business_receipt_reviews`. Deren bisherige
Schema-/Guarddefinitionen und gespeicherte Checksummen werden nicht verändert.
Vor einer neuen Quellenübernahme werden Originalbytes und Dokument-/Review-
Hashes tatsächlich geprüft; gespeicherte Hashangaben allein genügen nicht.

## Domänengrenze und Wiederherstellung

`Accounting(office,clock=…)` ohne DDL: `status(actor)`, `accounts(actor)`,
`create_account(actor,data)`, `update_account(actor,id,data)`,
`payment_sources(actor,limit=50,offset=0)`,
`receipt_sources(actor,limit=50,offset=0)`,
`events(actor,limit=50,offset=0)`, `event(actor,id)`,
`import_payment(actor,data)`, `payout(actor,data)`.

Der lokale SQLite-Restore setzt bei vorhandenem Business-Schema ebenfalls
`financial_reconciliation_required` und eine neue `restore_id`; historische
Legacy-Sicherungen bleiben lesbar. Der PostgreSQL-Weg erhält seine vorhandene
Datenschutz-/Finanzsperre. Normale Migration setzt keine Restoresperre.
Neue Accounting-Daten werden bei Restore niemals gelöscht oder als neue
Geldflüsse erneut importiert.

Der Betreiberabgleich wird um einen expliziten Accounting-Nachweis ergänzt:
vorhandene Quellen-/Geldflussstände müssen mit dem wiederhergestellten Bestand
und den unabhängig geprüften Vorgängen seit dem Sicherungszeitpunkt
abgestimmt sein. Ein Vergleich zweier aus derselben alten Sicherung berechneter
Hashes ist allein keine Vollständigkeitsprüfung. Der konkrete versionierte
Nachweis, Operatorpfad und lokale Freigabebefehl werden gemeinsam mit ihren
Tests dokumentiert; es gibt dafür keine gewöhnliche HTTP-Benutzeraktion.

## Betreiberabgleich

Bei installiertem `business_accounting` ohne zusätzliches Zuordnungsmodul
verlangt der Betreiberpfad einen JSON-Prüfbericht mit **genau** folgenden
Feldern. Mit E1b-1 gilt für neue Freigaben stattdessen
[Schema 3 mit kombiniertem Horizont](CRM_ERP_EUER_E1B1_API.md#restore-und-clients).
Mit zusätzlichem Komponentenmodul ohne Erstattungsmodul gilt
[Schema 4](CRM_ERP_EUER_E1B2_API.md#wiederherstellung-und-clients).
Mit Erstattungsmodul gilt
[Schema 5](CRM_ERP_EUER_E1B3A_API.md#restorehorizont-und-historische-betreiberquittungen).

```json
{
  "schema": 2,
  "restore_id": "32 Hexzeichen der aktuellen Wiederherstellung",
  "reviewed_by": "Name der prüfenden Person",
  "reviewed_at": "ISO-Zeitstempel mit Zeitzone",
  "number_horizons": [],
  "outbound_reconciled": true,
  "accounting_horizon": {
    "schema_version": 1,
    "accounts_count": 0,
    "account_versions_count": 0,
    "cash_events_count": 0,
    "source_links_count": 0,
    "max_sequence": 0,
    "sha256": "64 Hexzeichen des gespeicherten Accountingstands"
  },
  "accounting_reconciled": true,
  "accounting_external_review": {
    "reviewed_since_backup": true,
    "evidence_sha256": "64 Hexzeichen des unabhängigen Prüfungsnachweises",
    "note": "Geprüfte Quellen, Zeitraum und Ergebnis des Abgleichs seit der Sicherung"
  }
}
```

`number_horizons` enthält weiterhin je tatsächlich vorhandener Nummernserie
`company_id,series,year,last_value` und muss den wiederhergestellten Zählern
entsprechen. `reviewed_by` benötigt 1–200 Zeichen, `note` 1–2000 Zeichen.
`accounting_horizon` entspricht exakt dem ausschließlich lesenden
`business_accounting.restore_horizon(office)`; der Hash umfasst deterministisch
sortierte eigene Konten-/Versions-, Geldfluss-, Herkunfts- und Requestzeilen.
Der Hook erzeugt keine Tabellen und liefert bei fehlendem Modul `None`.
Ein installiertes, auch leeres Accountingmodul ohne zusätzliches
Zuordnungsmodul verlangt Schema 2; ohne Accounting bleibt der bisherige
Schema-1-Bericht gültig. Der unveränderte E1a-Horizont ist bei installiertem
E1b-1 ein Teil des erweiterten Schema-3-Berichts.

`accounting_reconciled` bestätigt den gespeicherten Vorjournal-/Quellenstand.
`accounting_external_review` bestätigt zusätzlich die unabhängige Prüfung der
Zahlungen und Quellen seit dem Sicherungszeitpunkt. Der referenzierte Nachweis
ist separat aufzubewahren. Die Software kann weder seine fachliche Richtigkeit
noch die Vollständigkeit externer Vorgänge aus einem Hash ableiten. Ein aus
derselben Sicherung erzeugter Vergleich ersetzt diese Prüfung nicht. Der
Betreiberbefehl berechnet den Hash des **vollständigen** Prüfberichts aus den
tatsächlich gelesenen Bytes und speichert ihn in der bestehenden unveränderlichen
Freigabehistorie. Eine identische bestätigte Wiederholung ist wirkungsfrei.

PostgreSQL behält den bestehenden Operatorpfad, die getrennte Datenbankrolle
und die Prüfung auf gestoppte Datenbanknutzer. SQLite wird ausschließlich über
`scripts/reconcile-accounting-restore.py --database DATEI --evidence BERICHT
--application-stopped` freigegeben. Alle Apps und Server dieser lokalen
Datenbank müssen vorher vollständig beendet werden. Der Schalter ist eine
ausdrückliche Betreiberbestätigung; er beweist nicht die Abwesenheit anderer
Prozesse. Die reine SQLite-Verbindung öffnet nur eine vorhandene Datei ohne
Office-Konstruktor/Migration und hält eine exklusive Schreibtransaktion.
Insbesondere im WAL-Modus bedeutet die SQLite-Sperre keine verlässliche
Erkennung aller noch laufenden Leser. Der bisherige allgemeine
`reconcile_financial_restore` lehnt SQLite weiterhin ab. Es gibt keine
HTTP-Freigabe und keinen automatischen Wiederanlauf von Finanzaktionen.

Zur Ermittlung des tatsächlich gespeicherten Stands dient zuerst
`scripts/reconcile-accounting-restore.py --database DATEI --inspect`.
Dieser vom Freigabeaufruf getrennte Modus öffnet die vorhandene Datenbank mit
`mode=ro` in einem konsistenten Lesesnapshot. Er liefert `inspection_only:true`,
das benötigte `evidence_schema`, Restore-ID/Sperren, Nummernhorizonte und den
Accountinghorizont; keine Prüferidentität, Prüfungserklärung oder Freigabe.
Er ist somit **kein fertiger Prüfbericht**. `--inspect` und `--evidence` können
nicht kombiniert werden. Die Inspektion benötigt keine Stoppbestätigung,
verändert keine Daten und legt keine fehlende Datenbank an.

Der zusätzliche Nachweis `backend/online/test_accounting_http.py` prüft
Accounting-/Finance-Rechte, unzulässige Eingaben, Schema-2-Pflicht und falsche
Horizonte, unabhängige Prüfbestätigung, konkurrierende SQLite-Schreiber sowie
einen tatsächlichen Restore mit anschließendem CLI-Aufruf. Nachweisdateien mit
doppelten JSON-Feldern, ungültigem UTF-8, übermäßiger Größe, öffentlichen
POSIX-Rechten oder Symlinks werden abgewiesen; eine fehlende Datenbank wird
nicht neu angelegt. Die Freigabe verändert weder ursprüngliche Zahlungen und
Belegprüfungen noch den gebundenen Accountingstand. Sie erzeugt genau eine
Freigabequittung, deren Hash den gelesenen Berichtsbytes entspricht.

Prüfstand 02.11.2026: **8 neue Grenztests**, gemeinsam mit den unabhängigen
Accountingreisen sowie bestehenden Backup-, Schema- und Portalrestorefällen
**41 bestandene Tests**; Protokoll
`work/verification/accounting-http-restore.log`. Der PostgreSQL-Operatorpfad
und seine Runtime-Rollengrenze werden zusätzlich in der gesonderten echten
PostgreSQL-Integrationssuite geprüft. Diese technischen Nachweise ersetzen
keine externe Bestandsprüfung eines realen Betriebs.
