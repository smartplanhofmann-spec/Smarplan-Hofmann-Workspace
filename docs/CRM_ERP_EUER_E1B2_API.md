# E1b-2: dokumentarische Beleganteile – Implementierungsvertrag

Stand: 02.11.2026, Basis `a8fa548`. Dieser Abschnitt ist implementiert;
ausgeführte Prüfungen stehen im [Fortschritt](CRM_ERP_FORTSCHRITT.md) und
im [gebundenen Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_E1B2.json).
Er erfüllt den nächsten Teil des [E1b-Plans](CRM_ERP_EUER_E1B_ENTWURF.md).
Eine Fertigmeldung des Gesamtziels erfolgt erst nach dessen tatsächlicher Abnahme.

## Fachlicher Umfang

Ein bereits bestätigter Geldfluss erhält belegte Netto-/Steuerkomponenten.
Der Benutzer wählt **einen ganzen unveränderlichen Quellenanteil** und bestätigt
die Bruttoverteilung auf seine archivierten Gruppen. Ein Quellenanteil ist:

- eine ursprüngliche `business_payment_allocations`-Zeile einer übernommenen
  Kundeneinnahme;
- eine zusätzliche bestätigte E1b-1-Zuordnung derselben Art;
- eine einzelne bestätigte Lieferantenauszahlung aus E1a, gebunden an ihre
  feste Eingangsbeleg-Prüfversion.

Die Quellenanteile bleiben einzeln identifizierbar; eine aufsummierte effektive
Zuordnung allein ersetzt diese Identität nicht. Jeder Anteil wird insgesamt
höchstens einmal dokumentiert. `portion_id` ist SHA-256 über kanonisches JSON
`{kind:<original_allocation|additional_allocation|supplier_payout>,id:<Quell-ID>}`.
Unzugeordneter Zahlungsrest bleibt ungeklärt. Die Aufteilung erzeugt keine
Zahlung, Rechnungszuordnung, neue OP-Wirkung oder Steuerbuchung.

Normale positive finale EUR-Rechnungen ohne Abschlags-/Schluss-/Stornobeziehung
sind unterstützt. Ursprüngliche Kundenzahlungen mit fehlender oder uneinheitlicher
Kundenbindung über ihre alten/zusätzlichen Belege bleiben lesbarer Klärungsfall
(`source_customer_unresolved`). Aktueller OP, `fully_allocated`, vollständig bezahlte Rechnung,
vollständig ausgezahlter Beleg und inaktives Geldkonto sperren für sich genommen
keine dokumentarische Aufteilung. Vorhandene Erstattungen geben **keine**
Gruppenkapazität frei; sie verbieten für sich genommen aber auch nicht die
Dokumentation eines noch verfügbaren ursprünglichen Einnahmenanteils.
Erstattungsursprünge, Rücknahme von Komponenten und erneute Nutzung freigegebener
Komponenten werden im folgenden Abschnitt entwickelt.

Eine neue Aufteilung einer Lieferantenauszahlung verlangt, dass die neueste
Prüfversion noch exakt zur eingefrorenen Auszahlung passt. Ein späterer
Prüfwechsel sperrt nur neue Aufteilungen; historische Aufteilungen und identische
Quittungen behalten ihre feste alte Prüfversion.

## Quellenprüfung und Centregel

Ausgangsrechnungen werden am unveränderten finalen Payload-/PDF-/XML-Archiv
geprüft. Der lokale Validator vergleicht die gespeicherten normalen Positionen
und Summen mit der vorhandenen `calculate_positions`-Funktion. Zusätzlich
validiert er eindeutige vollständige Gruppenidentitäten, kanonische Centwerte
und exakte Summen. `tax_breakdown` enthält `rate,category,reason,net,tax`;
Gruppenbrutto ist exakt `net+tax`. Die Gruppenidentität bindet Beleg-ID,
Archivhashes und vollständige archivierte Gruppendaten; kein Listenindex,
Payment-/Eventhash oder veränderlicher OP-Hash erzeugt einen eigenen Pool.

Bei Eingangsbelegen gibt es genau eine Gruppe aus den bestätigten Gesamtwerten
der konkreten Prüfversion. Poolbindung: Beleg-ID, Originalhash, Prüfversion und
Prüfhash. Es wird kein Steuersatz aus dem Verhältnis der Summen geraten.

Alle Gruppen haben `N>=0,T>=0,G=N+T`. Gültige Nullgruppen bleiben Bestandteil
des Quellenbeweises, werden aber nicht als verteilbare Gruppe angeboten.
Negative Gruppen oder widersprüchliche Summen sind nicht unterstützt. Für
jede positive Gruppe werden **über alle Geldflüsse derselben Gruppe hinweg**
die kumulativen Bruttocents `C` geführt. Rechnung ausschließlich mit ganzen
Centzahlen; ohne Float oder unkontrollierten Decimal-Kontext:

`Tax(C) = floor((2*C*T + G) / (2*G))`, `Net(C) = C - Tax(C)`.

Eine neue Zeile erhält die Differenz zwischen neuem und vorherigem kumulativem
Stand. Es gelten `C<=G` und exakte Zeilen-/Anteils-/Gruppensummen. Beispiel:
119,00 aus 100,00/19,00, in 39,67 / 39,67 / 39,66 bezahlt, ergibt
33,34/6,33; 33,33/6,34; 33,33/6,33. Eine spätere Zahlung oder ein früheres
Zahlungsdatum verteilt bereits bestätigte Cents nicht neu.
Eine ganze historische Überzahlungsportion, die nicht mehr in den verfügbaren
Gruppenrahmen passt, bleibt ungeklärt; sie wird nicht gekürzt oder in einen
automatisch als netto/steuerfrei behandelten Rest umgewandelt.

Der ganze Quellenanteil ist die feste Summe einer Bestätigung. Bei mehreren
Gruppen gibt der Benutzer die Bruttocents ausdrücklich an; keine proportionale
Vorbelegung über verschiedene Gruppen. Bei einer Gruppe darf der Client deren
Betrag mit dem ganzen Anteil vorbelegen. Nur positive Gruppenbeträge werden
gesendet; ausgelassene Gruppen bedeuten null. Die Summe muss exakt dem
Quellenanteil entsprechen und jede Gruppe ihren Rest einhalten.

## Daten, Rechte und Historie

Neues additives Modul `business_accounting_components`, Feature
`accounting_document_components`, bestehendes Unternehmensmodul `finance`.
Abhängigkeiten: E1a und E1b-1 müssen vollständig installiert sein. Neue Tabellen:

1. `business_accounting_component_entries`: unveränderlicher bestätigter
   Quellenanteil, globale Sequenz, Eventrevision, Quellen-/Zustandsbindung,
   eingefrorene Antwort und Quellenbeweis, Akteur/Zeit; `portion_id` eindeutig.
2. `business_accounting_component_lines`: feste Gruppenzeilen je Eintrag,
   Gruppen-ID, Netto-/Steuer-/Bruttocents, kumulativer Stand vorher/nachher und
   unveränderte Gruppenbasis; eindeutige Kombination Eintrag/Gruppe.
   Das Paar `(entry_id,group_id)` ist ihre dauerhafte Identität für spätere
   Erstattungsbezüge. Centwerte benötigen kanonische TEXT-Werte oder BIGINT,
   nicht PostgreSQL INTEGER.
3. `business_accounting_component_requests`: unveränderte Nutzlast und Hash,
   Benutzer/Anforderungskennung, bestätigter Eintrag; eindeutige Quittung.

SQLite schützt UPDATE/DELETE sowie REPLACE-Konflikte; PostgreSQL-Laufzeit erhält
nur SELECT/INSERT und keine DDL-Rechte. Historische DDL/Guard-Prüfsummen und
gespeicherte E1a-/E1b-1-Nachweise werden nicht verändert. Einträge, Zeilen,
Quittung und Audit entstehen in derselben vorhandenen serialisierten Transaktion.
Ein Fehler rollt sämtliche neuen Zeilen zurück.

Lesen verlangt global `accounting.read`, global `finance.read` und frische
vollständige Quellrechte des CashEvents. Bei Kundenzahlungen gehören alle alten
und zusätzlichen Projektzuordnungen dazu; ursprünglich unzugeordnete private
Zahlungen bleiben privat. Schreiben/Vorschau verlangt zusätzlich global
`accounting.prepare`, global `finance.write` und Schreibrecht auf alle
Quellprojekte beziehungsweise den Eingangsbeleg. Kandidaten können unter diesen
Schreibrechten gewählt werden; die lesende Historie bleibt separat nutzbar.

Globale Gruppenkapazität wird niemals nach Akteur gefiltert. Autorisierte
Belegaggregate sind sichtbar; fremde beitragende Payment-/Event-/Akteur-IDs,
Begründungen und deren Beweise erscheinen nicht im öffentlichen DTO.
Interne Beweise verwenden flache Referenzen mit Hashes, keine rekursiv
eingebetteten vollständigen früheren Einträge.

Identischer Replay prüft aktuelle Rechte, Modus/Restore-/Modulsperren und
historische Integrität vor Rückgabe der gespeicherten Antwort. Danach prüft er
nicht erneut aktuelle Gruppenreste, neuesten Review oder heutige Kandidaten.
Eine veränderte Nutzlast unter derselben Kennung liefert 409.
Die additive C1/C2-Wiederholungsregel im
[E1b-3b-Vertrag](CRM_ERP_EUER_E1B3B_API.md#replay-clients-und-fehler)
ergänzt ausschließlich Komponenten-Confirms um
`request_resolution:'not_accepted'` bei HTTP 409 nach geprüftem fehlendem
Receipt und vor neuen Schreibwirkungen. Vorherige Rechte-/Betriebs-/
Integritätsgates bleiben an ihrer Stelle und liefern keine solche Auflösung.
Unmarkierte 409 sowie 403/404/423, 5xx und Netzfehler erhalten einen unklaren
Komponentenauftrag; andere Operationen bleiben unverändert. Historische
C1-Antworten, Quittungen und Proofs ändern sich nicht. Der abgegrenzte Stand ist im
[E1b-3b-Nachweis](CRM_ERP_PRUEFNACHWEIS_E1B3B.json) geprüft.

## HTTP-Vertrag

Basis `/api/v1/business/accounting/components/events/{event_id}`.
IDs: 32 Kleinhexzeichen; Hashes/portion_id/group_id: 64 Kleinhexzeichen.
Bestehende Seitengrenzen: `limit` 1–100, `offset` 0–100000.
Neue Geldwerte: String `0.00` bis `999999999.99`, Eingabegruppen strikt positiv.
Unveränderte gültige Archiv-Gruppensummen dürfen größer sein; sie werden als
exakte kanonische Strings/Integercents gelesen und angezeigt. Der neue einzelne
Quellenanteil und die Eingabebeträge bleiben begrenzt. Clients verwenden für
gespeicherte Vergleiche beliebig große Ganzzahlen und keine Floatkonvertierung.
`reason`: einzeilig 1–1000 Zeichen. Unbekannte Felder, doppelte Queryparameter,
GET-Anfragekörper und POST-Queryparameter werden abgewiesen.

| Methode/Pfad | Antwort |
| --- | --- |
| GET Basis | State |
| GET `/portions?limit=50&offset=0` | Noch nicht dokumentierte Quellenanteile mit eigenem Status/Rest, paginiert |
| GET `/history?limit=50&offset=0` | Bestätigte Einträge, neueste Eventrevision zuerst, paginiert |
| POST `/preview` | Nebenwirkungsfreie Vorschau, 200, keine Quittung/Audit/Sequenzänderung |
| POST `/confirm` | Ausdrücklich bestätigter Eintrag, 201; identischer Replay gleiche Antwort |

`State`:
`{event_id,source_hash,revision,state_hash,source_kind,amount,currency,
documented_amount,undocumented_amount,unallocated_amount,eligible,blocked_reason,
writes_allowed,scope:'authorized_sources',tax_status:'unconfigured',
tax_result_available:false}`.
`source_kind`: `customer_receipt`, `supplier_payout`, `customer_refund`.
Sperrgründe: `refund_origin_unresolved`, `source_customer_unresolved`,
`unsupported_document`, `review_changed`, `group_capacity_exceeded`,
`unallocated`, `fully_documented`; `null` bei zulässiger Aktion.
`revision` zählt eigene Einträge; `state_hash` bindet zusätzlich die aktuelle
vollständige Quellenanteilsmenge. `undocumented_amount` umfasst auch nicht
zugeordnete und nicht unterstützte Beträge. Refunds sind lesbar, aber nicht
bestätigbar (`refund_origin_unresolved`).

`Portion`:
`{portion_id,kind,event_id,document_id,receipt_id,project_id,number,party_name,
amount,currency,payload_sha256,pdf_sha256,original_sha256,review_revision,
review_sha256,portion_state_hash,eligible,blocked_reason,groups}`.
Nicht anwendbare Felder sind `null`. `number`/`party_name` kommen aus dem
eingefrorenen Beleg/Prüfstand. `portion_state_hash` bindet stabile Quelle,
aktuellen zulässigen Beleg-/Reviewstand und **alle** schon bestätigten
Gruppenbeiträge, auch von anderen Geldflüssen. Nach einer konkurrierenden
Verteilung wird eine alte Vorschau dadurch ungültig.

`Group`:
`{group_id,rate,category,reason,net,tax,gross,documented_net,documented_tax,
documented_gross,remaining_net,remaining_tax,remaining_gross}`.
`rate/category/reason` sind bei der einzigen Eingangsgruppe `null`.
`net/tax/gross` sind die unveränderten ursprünglichen Gruppenbeträge;
aggregierte dokumentierte/übrige Beträge enthalten keine fremden Quellen-IDs.

Vorschaubody:
`{source_hash,expected_revision,state_hash,portion_id,portion_state_hash,
groups:[{group_id,amount}],reason}`.
Maximal 500 eindeutige positive Gruppen, Summe exakt Anteil. Die Vorschau
ordnet Zeilen stabil nach Gruppen-ID; die gespeicherte ursprüngliche
Befehlsnutzlast bleibt für exakten Replay erhalten.

`Preview`:
`{event_id,source_hash,expected_revision,state_hash,portion:Portion,amount,
net,tax,lines,reason,preview_hash,scope:'authorized_sources',
tax_status:'unconfigured',tax_result_available:false}`.
`Line`:
`{group_id,amount,net,tax,gross_before,gross_after,net_before,net_after,
tax_before,tax_after,remaining_gross}`.
`*_before/after` sind der globale dokumentierte Gruppenstand; `amount/net/tax`
die neue Differenz. Es wird keine steuerliche Periode berechnet.

Bestätigungsbody: Vorschaubody plus
`{request_id,preview_hash,confirmation:true}`.
`Entry`: Preview ohne `expected_revision,state_hash`, dafür
`{id,sequence,revision,previous_state_hash,created_by,created_at}`.

Domänenklasse `DocumentComponents(office,clock)` mit `state`, `portions`,
`history`, `preview`, `confirm`; gleiche Signaturen/Paginierung wie E1b-1.
Hilfsfunktionen `installed`, `validate_integrity`, `restore_horizon`.

## Wiederherstellung und Clients

Eigenes C1: `{schema_version:1,table_counts:{drei feste Tabellennamen:Anzahl},sha256}`
über alle eigenen Zeilen einschließlich Requests. Alte E1a-H1 und E1b-1-H2
bleiben unverändert. Mit Komponenten ohne Erstattungsmodul liefert der gemeinsame Operatorhorizont
`{schema_version:3,prejournal:<H1>,allocations:<A1>,components:<C1>}`.
Neue Freigaben verlangen Berichtschema 4, auch bei leerem Komponentenmodul.
Andere Berichts-/externen Abgleichsfelder bleiben gleich. Historische Parser
verwenden die festen Tabellenmengen ihrer eigenen Version; frühere identische
Quittungen sind nur bei bereits aufgehobener Sperre replaybar. Sie entsperren
keine neue Wiederherstellung. `--inspect` bleibt strikt lesend.
Mit [E1b-3a](CRM_ERP_EUER_E1B3A_API.md#restorehorizont-und-historische-betreiberquittungen)
ergänzt H4 den unveränderten C1-Teilhorizont um Erstattungsursprünge. Neue
Freigaben benötigen ohne Wiederverwendungsmodul dann Schema 5, auch bei leeren
Erstattungstabellen. Ist zusätzlich `business_accounting_capacity` installiert,
ergänzt der
[E1b-3b-Vertrag](CRM_ERP_EUER_E1B3B_API.md#horizonte-projektionen-und-nachweisgrenze)
H5 mit eigenem K1 über sechs neue Tabellen; neue Freigaben benötigen Schema 6,
auch bei leerem Modul. C1 und sämtliche historischen Horizonte/Parser behalten
ihre festen alten Tabellenmengen; die äußeren Betreiberfelder bleiben gleich.

Einstieg im vorhandenen Zahlungsnachweis „Beleganteile aufteilen“ bzw.
„Aufteilungen ansehen“. Quellenbetrag ist fest; mehrere Gruppen verlangen
ausdrückliche Bruttoeingaben. Vorschau und Bestätigung sind getrennt.
Produkttexte zeigen belegte Netto-/ausgewiesene Steueranteile und die offene
steuerliche Einordnung; keine internen Phasennamen/Hashes/rohen IDs.
Bei Eingangsbelegen heißt es „Ausgewiesener Steueranteil laut Prüfung“.
Keine Aussage „abziehbare Vorsteuer“ oder „fertige EÜR“.

Pendingbefehle binden Event, komplette ursprüngliche Gruppenliste und Vorschau
unverändert. Vor Anzeige alter Details werden Quellen-/Belegrechte frisch
geprüft; neutrale Wiederholungsdialoge geben keine gespeicherten Details preis.
Späte Antworten nach Rechte-/Sitzungs-/Kontextwechsel dürfen keine Ansicht
erneut füllen. Alte Server, Offline-/Lesemodus und gesperrtes Finanzmodul
bieten keine neue Schreibaktion an.


## Additive Erweiterung durch versionierte Erstattungsursprünge

Bei zusätzlich installiertem `business_accounting_refunds_v2` gilt für neue
Betreiberfreigaben [E1b-3c-Vertrag](CRM_ERP_EUER_E1B3C_API.md#h6-berichtschema-7-und-unveränderte-finanzprojektionen) mit H6 und
Berichtschema 7, auch bei leeren neuen Tabellen. H6 ergänzt ausschließlich
den eigenen fünf Tabellen umfassenden `refunds_v2`-Teilhorizont. Historische
Berichte bis H5/Schema 6 behalten ihre feste Struktur und entsperren keinen
neuen Restore. Der hier beschriebene ältere Teilvertrag bleibt erhalten;
ausgeführte Prüfungen und offene Integrationsarbeit der Erweiterung stehen im
[3c-Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_E1B3C.json).
