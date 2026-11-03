# Bankabgleich – stabiler API-/Clientvertrag

Stand 03.11.2026. Backend-Fach-, PostgreSQL-, HTTP- und Restore-Abnahmen sind abgeschlossen; Clientabnahmen erfolgen separat. Diese Datei ist der Vertrag für die getrennten Clients; die Endpunkte liegen unter `/business/bank` (native Sessionpfade `/bank`). Feature `bank_reconciliation`, Capability `business_bank_reconciliation`. Alle hier beschriebenen erfolgreichen JSON-Aufrufe liefern HTTP 200.

## Rechte, Modus und Wiederholung

Lesen erfordert global `bank.read`, `accounting.read`, `finance.read`. Schreiben erfordert zusätzlich `bank.prepare`, `accounting.prepare`, `finance.write`, aktives Finanzmodul, Schreibmodus sowie bestehende Financial-Release-/Runtimefreigabe. Bankbindungen speichern verlangt zusätzlich `bank.admin` und `accounting.admin`. Bankrechte geben keinen Zugriff auf private Personalakten. Die Bankdatei selbst enthält mögliche Personen-/Gehaltsinformationen; ihr Lesen ist eine ausdrückliche zusätzliche Bankdatenfreigabe.

Quellen und vorhandene Zuordnungen werden nur mit tatsächlichen aktuellen Quellenrechten gezeigt. Der vollständige Cash-Katalog darf bei unzugänglichen Quellen nicht als scheinbar vollständiger Teilbestand ausgegeben werden. Globale Bankberichte sind kein öffentliches Dashboard-/Assistentenmaterial.

Bestätigte Mutationen besitzen `request_id` (32 hex). Die Original-ID und der gesamte Originalbody müssen bei verlorener Antwort unverändert bleiben. Nur `409 request_resolution: not_accepted` bestätigt, dass ein neuer Vorgang sicher nicht angenommen wurde. Rollen-/Modus-/Noncekonflikte ohne diesen Marker bleiben ungeklärt. Replay erfordert aktuelle Rechte, auch wenn der historische Auftrag schon angenommen wurde.

Vorgeschlagene stabile Pending-Schlüssel: `bank-account-{account_id}`, `bank-import-{client_uuid}`, `bank-match-{transaction_id}`, `bank-reconciliation-{client_uuid}`. Vorschauen besitzen keinen request_id. Account benötigt keine separate Vorschau; alle anderen Schreibvorgänge fügen genau dem ursprünglichen Vorschauauftrag `request_id`, `preview_hash`, `confirmation:true` hinzu.

## Gemeinsame Ereignishülle

Gespeicherte Ereignisse sind **nicht flach**. Sie enthalten ihre Identität, Ersteller/Zeitpunkt, optional Revision/Vorgängerhash, `payload` und `content_hash`. SHA-256 bezieht sich auf die kanonische JSON-Hülle ohne `content_hash` (UTF-8, sortierte Schlüssel, keine unnötigen Leerzeichen). Geldbeträge sind exakte kanonische EUR-Dezimaltexte mit zwei Nachkommastellen. Die Clients rechnen keine Zahlen in float um.

Bankbindung: `account_id,revision,previous_hash,created_by,created_at,payload,content_hash`.

Auszug: `id,account_id,reference_key,file_sha256,created_by,created_at,payload,content_hash`.

Transaktion: `id,account_id,external_id,created_by,created_at,payload,content_hash`.

Zuordnung: `transaction_id,revision,previous_hash,created_by,created_at,payload,content_hash`. Noch nicht zugeordnete Transaktion: Revision 0, beide Hashes null, `payload:{links:[],reason:''}`.

Bankbericht: `id,account_id,period,created_by,created_at,payload,content_hash`.

## Kontobindung

`GET /accounts` → `{items:[Bankbindungen],available_accounts:[vorhandene EUR-Geldkonten Art bank],csv_contract:{version,columns,max_bytes,max_rows},external_connection:false}`. Der Benutzer legt ggf. zunächst das Geldkonto im bestehenden Accounting an.

`POST /accounts` erwartet exakt:

```json
{
  "request_id":"32hex",
  "account_id":"bestehendesGeldkonto",
  "account_revision":1,
  "revision":0,
  "iban":"DE89370400440532013000",
  "label":"Explizite Bankbezeichnung",
  "active":true,
  "coverage_from":"2026-01-01",
  "coverage_to":null,
  "reason":""
}
```

Antwort ist die genaue Bankbindung. `payload` enthält `account` (historischer Geldkontosnapshot), `iban,label,active,coverage_from,coverage_to,reason`. IBAN und Kontoführungsbeginn werden nach Erstanlage nicht umgedeutet. Ende ist explizites Datum oder null. Die Prüfziffer ist kein Nachweis des Kontoinhabers. Änderungen benötigen Grund und aktuelle Revision. Änderungen eines durch geschlossene Perioden belegten Bankprüfstands benötigen vorherige Wiederöffnung.

## Originalimport

`POST /import/preview` erwartet genau diese Felder:

```json
{
  "account_id":"32hex",
  "account_revision":1,
  "bank_revision":1,
  "statement_reference":"Auszug 2026-11",
  "period_from":"2026-11-01",
  "period_to":"2026-11-30",
  "opening_balance":"1000.00",
  "closing_balance":"1119.00",
  "filename":"auszug.csv",
  "delimiter":";",
  "content_base64":"OriginalbytesBase64",
  "complete_statement_confirmed":true
}
```

CSV-Kopf exakt in dieser Reihenfolge:

```csv
transaction_id;booking_date;value_date;amount;currency;counterparty;reference
TEST-001;2026-11-02;2026-11-02;119.00;EUR;Synthetischer Kunde;Synthetischer Zahlungseingang
```

5 MiB Original, höchstens 10.000 Zeilen, UTF-8 (BOM zulässig), explizites Komma/Semikolon, ISO-Daten, exakter Centbetrag. Positive Beträge sind Eingänge; negative Ausgänge. Gegenpartei und Verwendungszweck dürfen leer sein. Stabile externe ID ist Pflicht; keine automatisch erfundenen Fingerprint-IDs. Eine gültige Datei nur mit Kopf ist ein erlaubter Nullaktivitätsauszug, wenn der bestätigte Anfangs-/Endsaldo übereinstimmt. Nullbetragzeilen oder eine 0-Byte-Datei sind ungültig.

Vorschau → `{metadata,errors:[{line_number,message}],duplicates:[{line_number,transaction_id}],identity_checks:[{line_number,external_id,similar_external_ids,reason,confirmed}],duplicate_statement_id,can_import,total,preview_hash}`. `line_number` in Fehlern ist die tatsächliche CSV-Zeile einschließlich Kopf (oder null bei Auszugsfehler); in normierten Reihen/Bindings beginnt sie bei 1 für erste Datenzeile. `metadata` enthält `contract,account,bank,statement_reference,period_from,period_to,opening_balance,closing_balance,filename,delimiter,file_sha256,rows,complete_statement_confirmed,distinct_transaction_confirmations`. Jede `rows`-Zeile enthält `line_number` plus alle CSV-Spalten. Datei-/Saldo-/Identitätskonflikte dürfen nicht als erfolgreiche Teilübernahme dargestellt werden.

`POST /statements` = unveränderter Vorschauauftrag plus `request_id,preview_hash,confirmation:true`. ACK ist dauerhaft derselbe `{statement:<Ereignis>,lines:[{line_number,transaction_id,transaction:<Ereignis>}],original:{filename,sha256,path}}`. Der ACK enthält bewusst keinen später veränderlichen Zuordnungsstand.

`GET /statements?account_id=…&limit=50&offset=0` → `{items:[id,account_id,reference_key,file_sha256,content_hash,created_by,created_at als Objekte],next_offset}`. Maximal 100. `GET /statements/{id}` liefert dieselben Originaldaten plus `current` je Zeile (aktuelle Zuordnungsfassung). `GET /statements/{id}/original` liefert nach aktueller Freigabe die exakten CSV-Bytes; Client prüft Größe/Hash gegen Vorschau bzw. SHA-256 aus `original`.

Identische Header-only-Dateien dürfen mit eigener Referenz für unterschiedliche, nicht überlappende Nullaktivitätszeiträume gespeichert werden. Importiert der Benutzer nach neuer Vorschau eine identische bereits bestätigte Datei/Referenz, wird derselbe Auszug referenziert. Bekannte Transaktions-IDs mit identischem normiertem Inhalt dürfen in überlappenden Auszügen referenziert werden; sie erzeugen keine zweite Banktransaktion. Widersprüchliche Inhalte derselben ID oder wiederverwendeter Auszugsreferenz werden blockiert.

Inhaltsgleiche Buchungen mit verschiedenen externen IDs werden zusätzlich über normalisierte Buchungs-/Valutadaten, Betrag, Währung, Gegenpartei und Verwendungszweck erkannt. Die Vorschau enthält dafür `identity_checks`; eine neue Buchung bleibt gesperrt, bis der Benutzer ihre Eigenständigkeit am Original geprüft und dokumentiert hat. Optionales Eingabefeld `distinct_transaction_confirmations:{"externe-ID":"Belegter Grund für eine tatsächlich eigenständige Zahlung"}` ist in Vorschau und Bestätigung identisch mitzugeben. Nur konkret auffällige Zeilen dürfen bestätigt werden. Die Anwendung fasst echte gleichlautende Zahlungen nicht automatisch zusammen und speichert den Prüfgrund unverändert im Auszug.

## Explizite Zuordnung

`GET /transactions/{id}/candidates` → `{transaction,current,items:[{source,remaining,stale_existing_links}]}`. `source` enthält `source_kind,source_id,account,date,direction,amount,source_path,origin_hash,source_hash`. Unterstützte Arten: `cash_event`, `reviewed_external_cash`, `payroll_cash`. Die Payrollquelle ist öffentlich aggregiert; keine Personalidentitäten werden ergänzt. `remaining` berücksichtigt die eigenen bisherigen Zuordnungsteile als ersetzbar, andere aktive Zuordnungen als reserviert. `stale_existing_links` verhindert eine zusätzliche neue Zuordnung, bis veraltete Bindungen ausdrücklich aufgeklärt sind.

`POST /transactions/{id}/preview` erwartet:

```json
{
  "revision":0,
  "links":[{
    "source_kind":"cash_event",
    "source_id":"32hex",
    "source_hash":"64hex",
    "amount":"119.00",
    "date_difference_reason":""
  }],
  "reason":"Belegten Eingang ausdrücklich abgeglichen"
}
```

Vorschau → `transaction,revision` (neue Fassung), `previous_hash,links` (nun mit vollständigem `source` statt drei Eingabereferenzen), `reason,matched_amount,remaining,complete,preview_hash`. Unterschiedliche Geldfluss-/Bankbuchungstage benötigen `date_difference_reason`; das EÜR-Datum wird nicht verändert. Maximal 100 Teile je Transaktion; jede Quelle höchstens einmal in derselben Liste. Beide Seiten begrenzen die Gesamtkapazität. Mehrere Banktransaktionen dürfen unterschiedliche Teile derselben vorhandenen Geldbewegung belegen. Eine leere Liste hebt die Zuordnung mit Grund als neue Fassung auf.

`POST /transactions/{id}/matches` = exakt ursprünglicher Auftrag plus Bestätigungsfelder. ACK ist das unveränderliche Zuordnungsereignis; `payload` enthält `transaction,links,reason,matched_amount,remaining,complete,preview_hash`. Der Vergleich zur Vorschau muss alle Quellen/Teilbeträge binden. `GET /transactions/{id}/history?limit=50&offset=0` liefert `{items:[Ereignisse absteigend],next_offset}`.

## Monatsprüfstand und Export

`POST /reconciliations/preview` erwartet `{account_id,period:'YYYY-MM',statement_ids:[…],reason}`. Ein bis hundert verschiedene Auszüge. Der erklärte Kontoführungsbeginn/-schluss begrenzt den erforderlichen Nachweis im Monat; sonst ist der gesamte Kalendermonat lückenlos und ohne Überlappung zu belegen. Salden müssen zwischen aufeinanderfolgenden Auszügen anschließen.

Vorschau ist der vollständige Bericht: `schema_version:1,account_id,period,period_from,period_to,coverage_from,coverage_to,bank,statement_ids,statements:[{id,content_hash}],bank_rows,cash_rows,source_manifest,allocation_manifest,opening_balance,closing_balance,bank_movement_net,cash_movement_net,issues,complete,reason,state_hash,external_bank_verification:false,new_payment_created:false,tax_classification_changed:false,preview_hash`.

`bank_rows` enthalten `transaction,match,matched_amount,remaining,issues`. `cash_rows` enthalten `source,matched_amount,remaining`. `source_manifest` bindet sämtliche relevanten aktuellen Quellen (bei weggefallenen Quellen null); `allocation_manifest` bindet auch Zuordnungen außerhalb der gewählten Auszugszeilen, sofern sie dieselben Quellen nutzen. Dadurch bleibt eine später geänderte Teilzuordnung erkennbar. Mögliche Issuecodes: `statement_coverage_gap_or_overlap`, `statement_balance_discontinuity`, `statement_coverage_incomplete`, `source_changed`, `bank_amount_unmatched`, `cash_amount_unmatched`.

Unvollständige Berichte dürfen ausdrücklich dokumentiert werden, bleiben `complete:false` und sind kein Periodenabschlussnachweis. `POST /reconciliations` = exakt Vorschauauftrag plus Bestätigungsfelder. ACK ist `{record:<unveränderliches Ereignis mit Bericht als payload>,exports:{json,csv,pdf}}`; jedes Exportmanifest enthält `filename,media_type,size,sha256`.

`GET /reconciliations?account_id=…&period=…&limit=50&offset=0` liefert paginierte Metadaten und next_offset. `GET /reconciliations/{id}` liefert ACK plus `current` und `current_issues` aus neu geprüftem Quellenstand. Ein alter vollständiger Bericht ist bei `current:false` ausdrücklich veraltet. Historischer Export bleibt unverändert abrufbar über `GET /reconciliations/{id}/{json|csv|pdf}`. Clients prüfen vollständige Bytes gegen archiviertes Manifest; JSON muss genau dem Ereignis entsprechen.

## EÜR-Abschluss und Restore

`period_closure_proof(office,actor,period)` wird innerhalb der bestehenden EÜR-Transaktion ausschließlich bei neuem Abschluss aufgerufen. Nicht installiertes/noch unkonfiguriertes Bankmodul → null. Sonst für jedes zeitlich relevante eingerichtete Bankkonto ein aktueller vollständiger Bericht. Fehlender, unvollständiger oder veralteter Bericht →409. Resultat:

```json
{"schema_version":1,"period":"2026-11","reconciliations":[{"id":"32hex","account_id":"32hex","content_hash":"64hex","state_hash":"64hex"}],"scope":"explicitly_configured_bank_accounts","external_bank_verification":false}
```

Der Hook nutzt denselben transaktionalen PostgreSQL-Lock wie Bankimporte und Zuordnungen. Historische rein manuelle EÜR-Abschlüsse werden nicht umgeschrieben. Neue Änderungen an betroffenen bereits geschlossenen Monaten müssen die vorhandene explizite Wiederöffnung durchlaufen.

Sieben stabile Tabellen stehen in `business_bank_reconciliation.TABLES`. `restore_horizon()` liefert `{schema_version:1,table_counts:{genau diese sieben Tabellen},sha256}`; der Hash umfasst kanonisch sortierte vollständige Zeilen und anstelle großer Originalbytes deren bereits verifizierte SHA-256. Der Restore-Validator prüft Konto-/Datei-/Bankzeilen-/Zuordnungs-/Berichtsbezüge, Salden, Typen, Hashketten und bestätigte Kapazitäten. Technische Requests enthalten nur Referenzen, keine vollständigen Bank-ACKs.

`validate_period_closure_proof(office,proof,period)` validiert ausschließlich den historischen Bericht (ID, Konto, Content-/Statehash, Monat und damalige Vollständigkeit). Es vergleicht keinen heutigen Bankzustand. So bleiben frühere Abschlüsse nach ordnungsgemäßer Wiederöffnung und Korrektur prüfbar. Falsche oder fehlende historische Referenzen ergeben `ValueError`; ein fehlender aktueller Abschlussbericht ergibt beim neuen Abschluss dagegen HTTP 409.


## Client-Transportgrenzen

Nur die definierten Bank-JSON-Endpunkte erlauben in Browser und Flutter maximal
128 MiB Antwortdaten; das bindet auch Import-/Zuordnungs-/Berichtsquittungen.
Andere JSON-Endpunkte behalten ihre bisherigen Grenzen. Originaldateien bleiben
auf 5 MiB begrenzt, heruntergeladene Exporte werden zusätzlich gegen ihr
unveränderliches Größen-/Hashmanifest geprüft. Ein lokal überschrittenes
Antwortlimit bestätigt keine Ablehnung des ursprünglichen Auftrags: dessen
Eingabe und Anfrage-ID bleiben für die Aufklärung erhalten.
