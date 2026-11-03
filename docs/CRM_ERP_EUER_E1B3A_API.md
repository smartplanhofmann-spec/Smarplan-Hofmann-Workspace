# E1b-3a: belegte Erstattungsursprünge – Implementierungsvertrag

Stand: 03.11.2026. Implementierungsvertrag auf Grundlage
des abgeschlossenen E1b-2-Stands `81a42b3` (Nachweisbindung `2261712`).
Dieser Abschnitt ist implementiert. Tatsächlich ausgeführte Prüfungen stehen
im [Fortschritt](CRM_ERP_FORTSCHRITT.md) und im
[gebundenen Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_E1B3A.json).
Eine Gesamtabnahme wird daraus nicht abgeleitet.
Grundlage: [E1b-Plan](CRM_ERP_EUER_E1B_ENTWURF.md) und
[dokumentarische Komponenten](CRM_ERP_EUER_E1B2_API.md).

## Umfang und unveränderliche Grenzen

Neues additives Modul `business_accounting_refunds`, Feature
`accounting_refund_origins`, bestehendes Unternehmensmodul `finance`.
Abhängigkeiten: E1a, E1b-1 und E1b-2 sind vollständig installiert.

Ein bereits übernommener echter Kundenerstattungs-Geldfluss erhält eine
ausdrücklich bestätigte Ursprungsbindung. Ein Befehl verwendet **genau eine
ganze ursprüngliche Refund-Allocation** aus `business_payment_allocations`.
Diese Zeile muss zu dem im E1a-CashEvent eingefrorenen `business_payments`-
Datensatz mit `kind:'refund'`, Richtung `out` und Währung EUR gehören.
Es gibt keine editierbare Teilmenge dieser Refundportion.

Die Herkunft wird aus einem oder mehreren bestehenden dokumentarischen
Einnahmen-Lots gewählt. Ein Lot ist genau die unveränderliche
`business_accounting_component_lines`-Zeile mit der dauerhaften Identität
`(entry_id,group_id)`. Der ganze Refundanteil darf mehrere Lots desselben
Belegs teilweise oder vollständig zurücknehmen. Zwei Lots können dieselbe
`group_id` und verschiedene `entry_id` haben; sie bleiben getrennte Ursprünge.
Ihre ausdrücklich eingegebenen Beträge müssen genau die Refundportion ergeben.

`portion_id` ist SHA-256 über kanonisches JSON
`{kind:'original_refund_allocation',id:<ursprüngliche Allocation-ID>}`.
Diese Identität und die zugrunde liegende Allocation-ID sind jeweils global
eindeutig dokumentierbar, unabhängig von Nutzer und Anforderungskennung.

Die Refund-Allocation wirkt bereits negativ auf OP und Zahlungsprojektion.
Die neue Ursprungsbindung erzeugt **keine zusätzliche Finance-Wirkung**,
keinen neuen CashEvent, keine Bankauszahlung und keine Änderung an `reverses`.
Unzugeordnete Refundbeträge werden in diesem Abschnitt nicht nachträglich
Rechnungen zugeordnet; sie bleiben ausdrücklich ungeklärt.

Rücknahmecents werden exakt festgehalten, geben aber in E1b-3a **keine
Gruppenkapazität frei**. Es entstehen keine neuen Verteilungsabschnitte und
keine Wiederbelegung. E1b-2 rechnet seine positiven Komponenten unverändert
weiter; eine weitere Einnahme kann deshalb weiterhin an ausgeschöpfter
Gruppenkapazität scheitern. Der anschließende Abschnitt E1b-3b behandelt die
versionierte Übernahme und Wiederverwendung genauer Restcents.

`capacity_released:false`, `tax_status:'unconfigured'` und
`tax_result_available:false` gelten in State, Vorschau und Eintrag dieses
Abschnitts. Eine Ursprungsbindung ist weder Steuerbuchung noch Umsatzsteuer-
Gegenbuchung, Vorsteuerkorrektur, fertige EÜR oder Beweis einer Bankausführung.

## Quellen, Belegidentität und Zeit

Die Refundquelle benötigt über alle ursprünglichen Rechnungszuordnungen
hinweg eine gemeinsame nicht leere unveränderliche `customer_id`.
Mehrkunden-/NULL-Kundenquellen bleiben lesbar und sind
`source_customer_unresolved`. Aktuelle Änderungen am Projektkunden ersetzen
keine archivierte Dokumentkundenbindung.

Jedes gewählte Lot stammt aus einem gültigen E1b-2-Einnahmeneintrag mit
`source_kind:'customer_receipt'`, einer gewöhnlichen positiven finalen
EUR-Rechnung und einem positiven eingefrorenen Lotbrutto. Lieferantenauszahlungen
und Refunds sind keine Ursprungslots für diese Kundenerstattung.
Die `document_id` des Lots muss **exakt** der `document_id` der Refund-Allocation
entsprechen. Ein gleicher Kunde allein genügt nicht. Kundenbindung und
Währung müssen ebenfalls übereinstimmen.

Eine spätere Stornogutschrift, weitere Zahlung oder Erstattung macht einen
bereits gültigen historischen Einnahmen-Lot nicht ungültig. Die Ursprungsbindung
an einen solchen Lot ist auch nach Stornierung der Rechnung erlaubt. Die
aktuelle E1b-2-Kandidatensperre für neue positive Komponenten wird nicht als
Sperre dieser Rücknahme wiederverwendet. Unterstützt sind ursprünglich normale
Rechnungen; Abschlags-/Schlussrechnungsquellen bleiben Klärungsfälle.

Für eine neue Bindung gilt
`origin_event.cash_date <= refund_event.cash_date`, gleicher Tag eingeschlossen.
Maßgeblich sind die bestätigten Zahlungsdaten der CashEvents, nicht
`booking_date`, Importreihenfolge, Komponenten-Erstellzeit oder laufende Sequenz.
Ein Lot darf erst nach dem tatsächlichen Erstattungsdatum dokumentiert worden
sein. Verschiedene Geldkonten sind erlaubt; ein inzwischen inaktives Konto
sperrt die Ursprungsbindung nicht.

E1a-Originalbeweise, endgültige Payload-/PDF-/XML-Archive und der historische
C1-Eintrag samt Linien, Gruppenbasis, Quellen- und Anfragequittung werden
geprüft. Ein gültiger gespeicherter Hash allein ersetzt diese Beziehungen
nicht. Gespeicherte Quellenfehler führen zu 409; sie werden nicht gerundet,
gekürzt oder still als leerer Bestand behandelt.

## Exakte Rücknahmeregel und zwei getrennte Grenzen

Für einen Ursprungslot gelten seine **eingefrorenen tatsächlichen** Centwerte
`N` netto, `T` ausgewiesener Steueranteil und `G=N+T>0` brutto. Für den
kumulativ gebundenen Rücknahmebetrag `R` dieses Lots gilt ausschließlich:

`ReturnedTax(R) = floor((2*R*T + G) / (2*G))`

`ReturnedNet(R) = R - ReturnedTax(R)`.

Eine neue Zeile erhält die Differenz zum vorherigen kumulativen Stand.
Es wird nicht erneut mit dem Verhältnis der gesamten Rechnungsgruppe gerechnet.
Bei vollständiger Rücknahme werden exakt die ursprünglichen N/T/G-Cents des
Lots erreicht. Restwerte sind separat `G-returned_gross`, `N-returned_net`
und `T-returned_tax`; sie bleiben nicht negativ.

Unter derselben serialisierten Transaktion werden beide Grenzen geprüft:

1. Die ganze konkrete Refundportion wurde noch nicht gebunden. Alle neuen
   Zeilen summieren sich exakt zu ihrem unveränderlichen Betrag.
2. Für jeden Ursprungslot bleibt die Summe **aller** bereits bestätigten und
   neuen Rücknahmebeträge höchstens dessen G. Kein Akteur-/Projektfilter und
   kein aktueller OP-, Rechnungs- oder Kontostand verändert diese Grenze.

Die Reihenfolge bestätigter Rücknahmen wird durch eine neue globale Sequenz
festgehalten. Alte, noch ungeklärte Refunds werden nicht automatisch einem Lot
zugewiesen oder aus dessen Rest herausgerechnet. Sie geben auch keine
Gruppenkapazität frei. Diese Ansicht betrifft den gewählten CashEvent und seine
berechtigten Ursprünge; sie behauptet keine vollständige Klärung aller
Erstattungen der Rechnung oder des Unternehmens. Noch nicht nach E1a übernommene
Finance-Refunds bleiben unverändert bestehen; E1b-3b muss sie vor einer späteren
Wiederverwendungsentscheidung ausdrücklich berücksichtigen.

## Berechtigungen, Integrität und Wiederholung

Lesen verlangt global `accounting.read` und global `finance.read` sowie den
vollständigen aktuellen Quellzugriff auf den Refund-CashEvent. Sobald Bindungen
bestehen, müssen zusätzlich **sämtliche bereits gebundenen Ursprungsevents**
vollständig lesbar sein, bevor State, Portions, History oder gespeicherte
Antworten ausgegeben werden. Ein Teilverlust versteckt den gesamten betroffenen
Refund-Ursprungsstand; keine teilweise offengelegten Summen oder `hidden_count`.

Portion-/Ursprungsauswahl, Vorschau und Bestätigung verlangen zusätzlich global
`accounting.prepare`, global `finance.write` und aktuelle Finance-Schreibrechte
für die vollständigen Quellumfänge des Refunds und aller bereits gebundenen
Ursprungsevents. Vorschau und Bestätigung prüfen außerdem **alle neu gewählten**
Ursprungsevents vor dem Lesen ihrer fachlichen Details und Beweise. Finance-
Schreibrechte schließen die jeweils nötigen Finance-Leserechte ein.

Die vollständigen Ursprungssichten umfassen auch später ergänzte E1b-1-
Projektzuordnungen. Ursprünglich private unzugeordnete Zahlungen behalten ihre
Owner-/Erstellergrenze. Die bloße Berechtigung für die Rechnung oder ihre
Gruppe ersetzt niemals den Zugriff auf den vollständigen Ursprungsgeldfluss.
Ursprungskandidaten ohne diese Rechte werden vollständig ausgelassen.

Globale Rücknahmestände eines berechtigten Ursprungslots werden unabhängig
vom Leser über alle Rücknahmen berechnet. Öffentlich erscheinen nur die
Lotaggregate und ein opaker Zustandshash, keine fremden beitragenden Refund-,
Event-, Akteur- oder Anfrage-IDs und keine fremden Begründungen. Interne
Integritätsprüfungen nutzen unveränderliche Quellen ohne Owner-Impersonation.

Vorschau und Bestätigung benötigen aktiven Businessmodus, aktives Finanzmodul,
abgeschlossenen Restore-/Finanzabgleich und die bestehende Runtime-Prüfung.
GET führt keine fachliche oder technische Schreibwirkung aus. Keine DDL im
Konstruktor; keine Quittung oder Auditzeile für die Vorschau.

Identischer `request_id` und unveränderte ursprüngliche Nutzlast liefern nach
frischen vollständigen Rechten, Betriebsgates und historischen Quellen-/
Linienprüfungen exakt den gespeicherten Entry zurück. Aktuelle Lotreste und
heutige Kandidaten werden danach nicht erneut auf den historischen Befehl
angewendet. Eine geänderte Nutzlast mit derselben Kennung ergibt 409. Eine
andere Kennung für eine bereits gebundene Refundportion ergibt ebenfalls 409.

Die historische Prüfung rekonstruiert den Lotstand vor der gespeicherten
globalen Sequenz aus sämtlichen früheren tatsächlichen Rücknahmezeilen. Sie
bindet die gespeicherten Vorher-/Nachherwerte daran; die bloße rechnerische
Konsistenz eines behaupteten Vorstands genügt nicht. Spätere Rücknahmen,
Stornierungen und zusätzliche Quellzuordnungen verändern alte Antworten nicht.

## HTTP und genaue Datenformen

Basis: `/api/v1/business/accounting/refunds/events/{event_id}`.
`event_id` bezeichnet den Refund-CashEvent, niemals die Finance-Payment-ID.
IDs und Anfragekennungen sind 32 Kleinhexzeichen; SHA-256-Werte,
`portion_id` und `group_id` sind 64 Kleinhexzeichen.

Neue Beträge sind kanonische Strings mit zwei Nachkommastellen bis
`999999999.99`; Eingabeanteile sind strikt positiv. Ausgaben für Netto-/Steuer-
und Restwerte dürfen `0.00` sein. Geldrechnung erfolgt mit ganzen Cents;
keine Floatkonvertierung. `reason` ist einzeilig, nicht leer, 1–1000 Zeichen.
`cash_date` ist ein ISO-Kalendertag. Zeitstempel sind UTC-ISO-Zeitpunkte.
Unbekannte Felder, doppelte Queryparameter, GET-Anfragekörper und sämtliche
POST-Queryparameter einschließlich eines JSON-Felds `_query` werden abgewiesen.

| Methode/Pfad | Ergebnis |
| --- | --- |
| GET Basis | State, 200 |
| GET `/portions?limit=50&offset=0` | Noch nicht gebundene ganze Refundportionen, 200 |
| GET `/origins?portion_id=<hash>&limit=50&offset=0` | Berechtigte passende Ursprungslots mit positivem Rest, 200 |
| GET `/history?limit=50&offset=0` | Bestätigte Einträge des Refundevents, 200 |
| POST `/preview` | Nebenwirkungsfreie Vorschau, 200 |
| POST `/confirm` | Bestätigter Entry, 201, auch bei identischem Replay |

Listen haben exakt `{items,total,next_offset,scope:'authorized_sources'}`.
`limit` ist standardmäßig 50, erlaubt 1–100; `offset` standardmäßig 0,
erlaubt 0–100000. `next_offset` ist ein zulässiger Folgeoffset oder null.
`total` zählt ausschließlich autorisierte Einträge. Sortierung: Portions nach
`portion_id`, Origins nach `cash_date,origin_event_id,entry_id,group_id`, History
nach `revision DESC,id`. Die Liste der Ursprungslots ist keine automatische
Zuordnungsempfehlung. Kein Filter oder Sortierparameter außerhalb dieser Tabelle.

`State` hat exakt:

```text
{event_id,source_hash,revision,state_hash,source_kind,amount,currency,
 cash_date,evidence_reference,reference,origin_documented_amount,
 origin_unresolved_amount,unallocated_amount,eligible,blocked_reason,
 writes_allowed,capacity_released:false,scope:'authorized_sources',
 tax_status:'unconfigured',tax_result_available:false}
```

`source_kind` ist `customer_refund`, `customer_receipt` oder `supplier_payout`.
Andere vorhandene CashEvent-Arten bleiben unter ihrer Art lesbar und sind
`not_customer_refund`. `source_hash` bleibt der unveränderte E1a-Quellenhash.
`revision` zählt eigene bestätigte Bindungen dieses Events, anfangs 0.
`state_hash` bindet den vollständigen unveränderlichen Refundquellenstand,
die ursprünglichen Refundportionen und die eigenen bisherigen Eintragsköpfe.

`origin_documented_amount` summiert die ganzen gebundenen Refundportionen;
`origin_unresolved_amount = amount-origin_documented_amount` enthält auch
unzugeordnete und nicht unterstützte Beträge. `unallocated_amount` ist der
unveränderte unzugeordnete Rest der ursprünglichen Finance-Zahlung; er wird
nicht nochmals zur ungeklärten Summe addiert. Bei einer anderen CashEvent-Art
sind dokumentiert 0 und ungeklärt der Eventbetrag; der ursprüngliche
Paymentrest beziehungsweise bei Supplier-Payouts `0.00` bleibt kenntlich.

Sperrgründe: `not_customer_refund`, `source_customer_unresolved`,
`unsupported_document`, `unallocated`, `fully_documented`; sonst null.
`eligible` bezeichnet eine zulässige noch ungebundene Refundportion, keine
Zusage ausreichender sichtbarer Ursprungskapazität. `writes_allowed` beschreibt
die aktuellen nötigen Rechte und Betriebsgates unabhängig davon.

`Portion` hat exakt:

```text
{portion_id,kind:'original_refund_allocation',event_id,document_id,
 customer_id,project_id,number,party_name,amount,currency:'EUR',
 payload_sha256,pdf_sha256,portion_state_hash,eligible,blocked_reason}
```

Die Angaben stammen aus der konkreten ursprünglichen Refund-Allocation und
dem unveränderten endgültigen Rechnungsarchiv. `portion_state_hash` bindet
diese Zeile, ihren E1a-Quellen-/Belegnachweis, die Kundenbindung und ihren
Bindungsstatus. Er ersetzt nicht die einzelnen Lotzustandshashes.
Nicht unterstützte ganze Portionen bleiben mit `eligible:false` sichtbar.
Bereits gebundene Portionen stehen ausschließlich in History. Für ein fehlendes
oder bereits gebundenes `portion_id` liefert die Origin-Kandidatensuche 409;
für eine vorhandene fachlich gesperrte Portion eine leere Kandidatenliste.

`Origin` hat exakt:

```text
{entry_id,group_id,origin_event_id,component_sequence,rate,category,tax_reason,
 document_id,customer_id,project_id,
 number,party_name,cash_date,evidence_reference,reference,currency:'EUR',
 amount,net,tax,returned_amount,returned_net,returned_tax,
 remaining_amount,remaining_net,remaining_tax,lot_state_hash}
```

`amount/net/tax` sind die eingefrorenen Centwerte dieser einzelnen C1-Linie,
nicht die Werte der ganzen Rechnung oder Steuergruppe. `cash_date`,
`evidence_reference` und `reference` stammen aus dem zugehörigen unveränderten
Einnahmen-CashEvent. `returned_*` und `remaining_*` sind globale Lotaggregate.
`lot_state_hash` bindet Originaleintrag, Originalzeile und alle bisherigen
Rücknahmebeiträge dieses Lots als flache Hashreferenzen. Ein konkurrierender
Anspruch gegen denselben Lot ändert diesen Hash. Öffentliche Aggregate zeigen
keine Identitäten fremder Erstattungsbeiträge.

`component_sequence` ist die positive globale Sequenz des ursprünglichen
C1-Eintrags. `rate`, `category` und `tax_reason` entsprechen exakt dem
archivierten Gruppensatz, der Steuerkategorie und ihrem Begründungstext
(`basis.reason`); sie sind keine neu abgeleitete steuerliche Einordnung.
Damit bleiben mehrere Lose desselben Geldflusses verständlich als
„Dokumentierte Aufteilung …“ mit Beleggruppe unterscheidbar. Rohe IDs ersetzen
diese Beschriftung nicht.

Die Ursprungsliste enthält nur positive Restlots derselben Rechnung, mit
passender Kundenbindung, passendem Zahlungsdatum und vollständigen aktuellen
Schreib-/Leserechten. Ein bereits vollständig zurückgenommener Lot wird nicht
angeboten. Fehlende oder ungeklärte Ursprünge werden nicht geschätzt.

Vorschaubody, exakt:

```text
{source_hash,expected_revision,state_hash,portion_id,portion_state_hash,
 origins:[{entry_id,group_id,lot_state_hash,amount}],reason}
```

Es sind 1–500 unterschiedliche Paare `(entry_id,group_id)` mit positiven
kanonischen Beträgen erforderlich. Gleiche Gruppe mit unterschiedlichen
Einträgen ist erlaubt. Summe exakt Refundportion, keine automatische Kürzung.
Vorschau und Antwort sortieren Linien nach `entry_id,group_id`; die ursprünglich
gesendete Arrayreihenfolge bleibt Teil der unveränderten Anfragequittung.

`Preview` hat exakt:

```text
{event_id,source_hash,expected_revision,state_hash,cash_date,
 evidence_reference,reference,portion:Portion,amount,net,tax,lines,reason,
 preview_hash,capacity_released:false,scope:'authorized_sources',
 tax_status:'unconfigured',tax_result_available:false}
```

Hier beziehen sich `cash_date`, Nachweisreferenz und Verwendungszweck auf die
Erstattung. `amount` ist der feste ganze Refundanteil; `net/tax` summieren die
neu dokumentierten Rücknahmecents aller Linien. `preview_hash` ist SHA-256 über
die vollständige kanonische Vorschau ohne das Feld `preview_hash`.

`Line` hat exakt:

```text
{entry_id,group_id,origin_event_id,component_sequence,rate,category,tax_reason,
 origin_cash_date,
 origin_evidence_reference,origin_reference,lot_state_hash,amount,net,tax,
 gross_before,gross_after,net_before,net_after,tax_before,tax_after,
 remaining_gross,remaining_net,remaining_tax}
```

`entry_id/group_id` identifizieren den **Ursprungslot**. `amount/net/tax` sind
die neue positive Rücknahme. `*_before/after` sind die über alle Erstattungen
kumulierten Rücknahmewerte dieses einzelnen Lots, niemals der Rechnungsgruppe.
`remaining_*` sind dessen danach verbleibende noch rücknehmbare Cents.
Die drei `origin_*`-Informationsfelder stammen aus dem ursprünglichen
Einnahmen-CashEvent. `lot_state_hash` ist dessen geprüfter Zustand vor diesem
Befehl; er bleibt in der historischen Linie unverändert.
`component_sequence` und die drei Gruppenfelder entsprechen dem gewählten
Origin und bleiben auch in der Historie sichtbar und an den C1-Beweis gebunden.

Bestätigungsbody: Vorschaubody plus exakt
`{request_id,preview_hash,confirmation:true}`.

`Entry` ist Preview ohne `expected_revision,state_hash`, dafür mit
`{id,sequence,revision,previous_state_hash,created_by,created_at}`.
`id` bezeichnet den neuen Refundbindungseintrag. Die dauerhafte Identität
einer neuen Rücknahmelinie ist `(Entry.id, Line.entry_id, Line.group_id)`.
Diese Identität, ihre positiven G/N/T-Cents und die gebundene Herkunft stehen
E1b-3b später als Rücknahmenachweis zur Verfügung, ohne bereits eine
Kapazitätsfreigabe zu behaupten.

Domänenklasse `RefundOrigins(office,clock=None)`:

```text
state(actor,event_id)
portions(actor,event_id,limit=50,offset=0)
origins(actor,event_id,portion_id,limit=50,offset=0)
history(actor,event_id,limit=50,offset=0)
preview(actor,event_id,data)
confirm(actor,event_id,data)
```

Weitere Modulhooks: `schema_statements`, `guard_statements`,
`protected_tables`, `runtime_privileges`, `methods`, `dispatch`,
`installed`, `validate_integrity`, `restore_horizon`.

## Persistenz und Transaktionen

Genau drei neue Tabellen, keine Änderung historischer Modul-DDL oder Guards:

1. `business_accounting_refund_entries`: `id` als Primärschlüssel,
   eindeutige positive globale `sequence`, `event_id` als FK auf CashEvents,
   positive Event-`revision` mit `UNIQUE(event_id,revision)`,
   `refund_allocation_id` als eindeutiger FK auf die ursprüngliche
   `business_payment_allocations`-Zeile, eindeutige `portion_id`, `source_hash`,
   `previous_state_hash`, kanonische `entry_json`/`entry_sha256`,
   kanonische `proof_json`, `created_by`/`created_at`.
2. `business_accounting_refund_lines`: `entry_id` als FK auf den neuen
   Refundbindungseintrag, `origin_entry_id`/`group_id` mit gemeinsamem FK auf
   `business_accounting_component_lines(entry_id,group_id)`;
   Primärschlüssel `(entry_id,origin_entry_id,group_id)`.
   Kanonische Centstrings für `amount,net,tax,gross_before,gross_after,
   net_before,net_after,tax_before,tax_after,remaining_gross,remaining_net,
   remaining_tax`; dazu fester `origin_line_sha256`. Index auf
   `(origin_entry_id,group_id,entry_id)` für globale Lotansprüche.
   Das öffentliche `Line.entry_id` entspricht hier `origin_entry_id`.
3. `business_accounting_refund_requests`: Primärschlüssel
   `(user_id,request_id)`, `event_id`, unveränderte kanonische
   `request_json`/`request_hash`, eindeutige `entry_id` als FK auf den neuen
   Refundbindungseintrag. Der Requesthash bindet Operation, Event-ID und
   vollständige ursprüngliche Nutzlast einschließlich Arrayreihenfolge.

Die Entry-Beweise binden den historischen Refund-CashEvent, die ganze alte
Allocation, das Rechnungsarchiv, die unveränderten Ursprungseinträge/-linien,
deren vollständige Quellenbeweise und alle zum damaligen globalen
Sequenzstand relevanten vorherigen Lotansprüche. Große Originalbytes werden
geprüft, nicht in neue JSON-Antworten kopiert. Verweise auf frühere neue
Einträge sind flache Schlüssel-/Hashreferenzen; keine rekursive Einbettung.

UPDATE/DELETE sind auf allen drei Tabellen gesperrt. SQLite schützt zusätzlich
INSERT-/REPLACE-Konflikte gegen sämtliche Primär- und Unique-Schlüssel, auch
bei deaktivierten rekursiven Triggern. PostgreSQL-Runtime erhält ausschließlich
SELECT/INSERT, keine UPDATE-/DELETE-/DDL-Rechte. Geldwerte bleiben TEXT-Centstrings
oder geprüfte BIGINT-Cents; PostgreSQL INTEGER genügt nicht als Geldspeicher.

Autorisierung, Quellen-/Vorschauprüfung, sämtliche Lotreste, globale Sequenz,
Entry, Linien, Quittung und Audit liegen in derselben vorhandenen Transaktion:
SQLite IMMEDIATE beziehungsweise die vorhandene PG-Advisory-Lock. Fehler nach
einer beliebigen Zeile rollen alles zurück. GET und Vorschau schreiben nichts.

## Fehlervertrag

- 400: unbekannte/fehlende Felder, unzulässige Filter, falsche Typen,
  nichtkanonische oder nichtpositive Eingabecents, doppelte Lotpaare,
  ungültige Begründung/Bestätigung und nicht exakt passende Anteilssumme.
- 403/404: fehlende globale Rechte beziehungsweise fehlender vollständiger
  Quellzugriff; keine verborgenen Details in Fehlermeldungen.
- 404: nicht vorhandener Event oder ausdrücklich angefragter neuer Ursprung,
  nachdem die vorhandenen notwendigen Zugriffe geprüft wurden.
- 409: ungeeignete Quelle, fremder Beleg/Kunde, Ursprung nach Refunddatum,
  ausgeschöpfter Lotrest, geänderter Quellen-/Portion-/Lot-/Vorschauhash,
  veraltete Revision, bereits gebundene Refundportion, Requestkonflikt,
  beschädigte gespeicherte Quelle, unvollständige Installation oder
  aktiver Restore-/Rückkehrmodus. Keine Teilwirkung.
- 423: fachlich deaktiviertes Finanzmodul für Vorschau/Bestätigung.
- 405: bekannte Route mit nicht unterstützter Methode.

Fehler beim Decodieren gespeicherter Zahlen, JSON-Strukturen oder Revisionen
werden zu Quellenkonflikten normalisiert. Neue Eingabefehler bleiben 400.

## Restorehorizont und historische Betreiberquittungen

`restore_horizon(office)` liefert R1:

```text
{schema_version:1,
 table_counts:{business_accounting_refund_entries:<count>,
               business_accounting_refund_lines:<count>,
               business_accounting_refund_requests:<count>},
 sha256}
```

Der Hash bindet alle vollständigen eigenen Zeilen einschließlich Requests,
deterministisch sortiert und zuvor auf Integrität geprüft. Vollständig
fehlendes Modul ohne Tabellen und Migrationsmarker ergibt null; jede
Teilinstallation, fehlende Abhängigkeit oder beschädigte Historie einen
Fehler. Kein DDL, keine Migration, kein Commit im Hook.

H1, A1 und C1 bleiben unverändert. Mit installiertem Refundmodul ohne
Wiederverwendungsmodul lautet der gemeinsame H4-Horizont exakt:

```text
{schema_version:4,prejournal:<H1>,allocations:<A1>,components:<C1>,refunds:<R1>}
```

Neue Betreiberfreigaben benötigen Berichtschema 5, auch bei leerem R1-Modul.
Die übrigen Berichts-/externen Abgleichsfelder gelten unverändert. Parser für
historische Berichtsstände behalten ihre jeweilige feste Tabellenmenge.
Ein bereits erfolgreich quittierter alter vollständiger Bericht ist nur nach
denselben Betreiber-/Stillstands-/Restore-ID-Prüfungen und bei bereits
aufgehobener Sperre wirkungslos wiederholbar. Ein alter Bericht entsperrt keine
neue Wiederherstellung; neue Freigaben benötigen den vollständigen aktuellen
H4-Horizont. `--inspect` bleibt rein lesend.

Ist zusätzlich `business_accounting_capacity` installiert, verlangt der noch
in Entwicklung befindliche, nicht freigegebene
[E1b-3b-Vertrag](CRM_ERP_EUER_E1B3B_API.md#horizonte-projektionen-und-nachweisgrenze)
H5 mit eigenem K1 über genau sechs neue Tabellen und neue Betreiberfreigaben
nach Schema 6, auch bei leerem Modul. H1/A1/C1/R1, historisches H4 und dessen
Schema-5-Parser bleiben unverändert; die äußeren Betreiberfelder bleiben gleich.
Eine historische Schema-5-Quittung entsperrt keinen neuen Restore.

## Clients und noch offene Erstattungen

Einstieg beim bestätigten Kundenerstattungs-Geldfluss: „Erstattungsursprung
zuordnen“ beziehungsweise „Ursprungsbindungen ansehen“. Ganze Refundportion,
Rechnung und Betrag sind fest. Kandidaten zeigen Zahlungsdatum,
Zahlungsnachweis-Referenz, Verwendungszweck und noch verfügbare konkrete
Lotcents. Keine automatische Ursprungsauswahl anhand ähnlicher Beträge oder
zeitlicher Nähe. Mehrere Lots derselben Steuergruppe bleiben unterscheidbar.

Der Benutzer gibt positive Rücknahmebeträge ein, prüft die vollständige
Vorschau und bestätigt gesondert. Die Oberfläche nennt dokumentierte Netto-/
ausgewiesene Steueranteile und macht deutlich, dass Gruppenkapazität noch
nicht wieder freigegeben wird. Keine Steuerperiode, automatische Gegenbuchung
oder fertige EÜR behaupten. Interne Phasenbezeichnungen, rohe IDs und Hashes
werden nicht als fachliche Produkttexte angezeigt.

Pendingbefehle behalten Event, Portion, vollständige ursprüngliche Originliste,
Beträge, Begründung, Anfrage-ID und Vorschau unverändert. Vor Anzeige alter
Details werden der Refund und alle bereits beziehungsweise neu ausgewählten
Ursprünge frisch autorisiert. Solange diese Prüfung nicht gelingt, bleibt der
Retrydialog neutral; keine lokal gespeicherten Namen, Beträge oder Referenzen.
Späte Antworten nach Rechte-/Sitzungs-/Eventwechsel dürfen eine neue Ansicht
nicht befüllen. Keine neue persistente Offlinewarteschlange. Fehlendes Feature,
Offline-/Lesemodus oder gesperrtes Finanzmodul verhindern neue Befehle.

Nach Bestätigung werden Refundstatus und Lotreste neu geladen. E1a- und C1-
Ansichten bleiben als ihre unveränderten historischen Nachweise erkennbar.
Ungebundene oder noch nicht importierte alte Refunds bleiben ungeklärt; kein
vollständiger Unternehmensabgleich wird aus dieser Einzelansicht abgeleitet.

## Gezielte Akzeptanznachweise

1. Ganze vorhandene Refund-Allocation einmal binden; andere Request-ID oder
   Nutzer erzeugen keine zweite Bindung. Finance, OP, originale Allocation,
   E1a-/C1-Antworten, alte Horizonte und Gruppenkapazität bleiben unverändert.
2. Zwei Lots derselben Gruppe aus unterschiedlichen Einträgen:
   39,67 = 33,34/6,33 und 39,67 = 33,33/6,34. Ganze Refundportionen
   26,44 / 26,44 / 26,46 verteilen sich jeweils 13,22+13,22,
   13,22+13,22 und 13,23+13,23. Neue Netto-/Steuersummen sind
   22,22/4,22; 22,21/4,23; 22,24/4,22. Vollständig exakt 66,67/12,67.
3. Beide ursprünglichen CashDates liegen vor oder am Refunddatum; spätere
   Komponenten-Erstellung bleibt zulässig. Späterer ursprünglicher Geldfluss
   wird abgewiesen. Spätere Stornierung erlaubt die Bindung eines echten alten
   Lots, öffnet aber keine neue positive Komponentenkapazität.
4. Zwei getrennte PG-Verbindungen konkurrieren um dieselbe Refundportion
   beziehungsweise den letzten Ursprungslotrest. Höchstens ein widersprüchlicher
   Befehl gewinnt; veraltete Vorschau scheitert ohne Teilwirkung.
5. Vollständige Refund-/Originrechte vor Details, Vorschau, Kandidaten und
   Replay. Spätere E1b-1-Projekterweiterung und Entzug eines einzigen nötigen
   Rechts sperren auch historische Anzeigen. Private Originalgrenzen bleiben.
6. Korrupte letzte Rücknahmelinie mit konsistent neu berechneten JSON-Hashes
   darf keinen erfundenen Vorherstand oder verkürzten Quellenanteil bestehen.
   Fremde globale Lotbeiträge werden vollständig geprüft, öffentlich nur
   aggregiert ausgegeben. Fehler nach erster Linie oder Audit rollen alles zurück.
7. SQLite UPDATE/DELETE/REPLACE-Schutz; echte PG-Laufzeitrechte und Guards.
   Migration erhält alte Quellen/Archive/Quittungen unverändert. Echter Restore
   blockiert neue Bestätigung und Replay bis zur vollständigen Schema-5-Freigabe;
   anschließend bleiben identische historische Antworten exakt erhalten.
8. Ein ungeklärter oder noch nicht nach E1a übernommener alter Refund wird
   weder automatisch gebunden noch als Gruppenkapazität freigegeben. R1 zeigt
   keine scheinbar vollständige steuerliche oder unternehmensweite Klärung.
