# E1b-3c: versionierte Erstattungsursprünge – Implementierungsvertrag

Stand: 03.11.2026. **Vertrag, nicht implementiert oder abgenommen.**
Quellbasis `5a6e22ca278d647b4889243688b04e52b308a5b9` (abgeschlossener
3b-Nachweispin; Implementierung `36f72a29e6074b8a06d470a59f0c03230037de1d`).
Dieser neue Vertrag gehört nicht zum 3b-Abschluss.

Grundlagen: [R1](CRM_ERP_EUER_E1B3A_API.md),
[C2](CRM_ERP_EUER_E1B3B_API.md),
[3c-Entwurf](CRM_ERP_EUER_E1B3C_ENTWURF.md). Bei Abweichungen gilt dieser Vertrag.
Die vorhandenen isolierten Rechen-/Reihenfolgehelper sind kein Nachweis einer
implementierten R2-Domäne oder einer vollständigen EÜR.

## Namen, Umfang und feste Grenzen

Neues additives Modul `business_accounting_refunds_v2`, Klasse
`VersionedRefundOrigins(office,clock=None)`, Feature `accounting_refund_origins_v2`.
Interner gemeinsamer Leser/Validator: `accounting_joint_ledger`; kein eigener
HTTP-Schreiber. Abhängigkeiten: vollständige E1a-, E1b-1-, C1-, R1- und
C2-Installation. Bestehendes Unternehmensmodul finance und bestehende Rechte.

R2 dokumentiert genau eine ganze ursprüngliche Refund-Allocation an einem
bereits übernommenen EUR-Kundenerstattungs-CashEvent. Sie darf ausdrücklich
gewählte C1-Lots, C2-Lots oder beide enthalten. Der ganze Betrag bleibt fest;
keine Teilbestätigung, automatische Auswahl oder Kürzung. Unzugeordnete
Refundreste und bisher nicht unterstützte Rechnungs-/Kundenfälle bleiben offen.

R2 ist nur für Rechnungen vorgesehen, die bereits mit allen Gruppen in C2
übernommen wurden. Noch nicht übernommene Rechnungen bleiben R1. Der erste
R2-Entry übernimmt die ganze Rechnung atomar in den R2-Refundschreiber; seine
ausgewählten Lots dürfen auch ausschließlich C1 sein. Das verlangt keine
vollständige Klärung anderer Refunds: Die noch offene Portion wird gerade erst
geklärt. Eine spätere Stornierung verhindert die Rücknahme gültiger alter Lots
nicht. Ein aktueller positiver C2-Kandidat ist keine Voraussetzung für R2.

R2-Rücknahmecents werden anschließend durch den unveränderten positiven
C2-Pfad in neue Restabschnitte übernommen. R2 selbst gibt keine Kapazität frei.
Keine neue Zahlung, Rechnungszuordnung, OP-/Mahnwirkung, Steuerperiode oder
Steuerbuchung. C2-Lots und ganze gemischte Portionen sind erst mit diesem
integrierten Schritt als Erstattungsursprünge unterstützt.

## Writerübergang und Identitäten

`portion_id` bleibt der R1-Hash der ganzen Original-Allocation:
SHA-256 über kanonisches `{kind:'original_refund_allocation',id:<Allocation-ID>}`.
Eine Allocation/portion_id darf über R1 und R2 zusammen höchstens einmal
gebunden sein. R2 prüft beide Claims unter dem gemeinsamen Schreiblock.

Ein unveränderlicher R2-Handoff je document_id bindet den vorhandenen C2-
Handoff, alle bis dahin vorhandenen R1-Entries/Linien dieser Rechnung und die
beobachtete globale R1-Sequenzgrenze. Er wird mit dem ersten R2-Entry eingefügt.
Danach sind neue R1-Bindungen dieser Rechnung gesperrt; R1-Bindungen anderer
Rechnungen bleiben zulässig. Der gemeinsame Validator prüft die eingefrorene
vollständige R1-Rechnungsmenge, nicht nur ausgewählte oder freigegebene Lots.

Die zusätzliche R1-Sperre liegt in der öffentlichen Domänenmethode: bei Preview
vor neuer Vorbereitung, bei Confirm erst nach frischen Sicherheitsgates,
historischer Integrität und erfolgreichem exaktem Receipt-Replay. Ein Feature-
Toggle oder eine unlesbare Teilinstallation öffnet den alten Writer nicht.

Ein Refundevent kann Portionen verschiedener Rechnungen und damit verschiedene
Writer enthalten. Writerentscheidung immer je Portion. Das neue R2-State zählt
R1+R2; alte R1-Antworten, Quittungen, Hashes und History bleiben unverändert und
führen weiterhin ausschließlich ihren eigenen R1-Nachweis.

Positive Lotidentität: `(origin_version,entry_id,group_id)` mit origin_version
c1 oder c2. Rücknahmelinienidentität intern:
`(refund_version,refund_entry_id,origin_version,origin_entry_id,group_id)`.
R1 ist ausschließlich origin_version c1. Versionsangaben gehören zu allen
neuen Schlüsseln, Hashes, Auswahlwerten und Referenzen; identische Roh-IDs in
verschiedenen Modulen dürfen nicht zusammenfallen.

## Exakte kumulative Rücknahme

Lotbasis sind die tatsächlichen unveränderlichen N/T/G-Cents der positiven
Linie. Für C2 ist das ihre damalige Abschnittszuweisung, niemals die aktuelle
Kapazität oder das Verhältnis der Rechnung. Für C1 enthält R_before sämtliche
gültigen bisherigen R1- plus früheren R2-Rücknahmen; für C2 sämtliche früheren
R2-Rücknahmen. Kein Akteurfilter und kein Reset beim R1→R2-Wechsel.

```text
Tax(R) = floor((2*R*lot_T + lot_G) / (2*lot_G))
Net(R) = R - Tax(R)
new_tax = Tax(R_before + amount) - Tax(R_before)
new_net = amount - new_tax
0 < amount <= lot_G - R_before
```

Die übertragenen R1-Netto-/Steuercents müssen exakt zum kumulativen R1-Gross
und zur ursprünglichen Lotbasis passen. Nicht den verbleibenden Lotrest als
neue Basis verwenden. Vollständige Rücknahme über beide Versionen erreicht
exakt die ursprüngliche Linie. Summe aller neuen Linien exakt Refundportion.

Beispiel: C1-Lot 39,67 = 33,33 + 6,34; R1 nimmt zunächst 13,22 = 11,11 + 2,11
zurück. Weitere 13,22 über R2 ergeben 11,10 + 2,12. Ein C2-Lot aus den ersten
13,22 hat dagegen genau 11,11 + 2,11. Eine gemischte R2-Portion 26,44 aus beiden
genannten Rücknahmen ergibt daher 22,21 + 4,23.

Jeder Ursprung muss exakt dieselbe archivierte document_id, customer_id und
EUR-Währung wie die Refundportion haben. origin.cash_date liegt spätestens am
refund.cash_date, gleicher Tag erlaubt. Kontoinaktivität und spätere
Stornierung ändern gültige historische Lots nicht. Aktuelle OP-Beträge sind
keine Lotrestgrenze.

## Rechte und nichtrekursive Autorisierung

Grundrechte wie R1: global accounting.read und finance.read; Vorschau,
Bestätigung und Kandidatenauswahl zusätzlich accounting.prepare, finance.write
und vollständige aktuelle Quellrechte. Businessmodus, aktives Finanzmodul,
Restore-/Finanzfreigabe und Runtimeprüfung bleiben vor dem Receiptlookup.

Der neue gemeinsame Zugriffsleser bildet vor Fachdetails eine endliche
relationale Hülle mit typisierten IDs und visited-Menge:

1. Ganze angefragte Refundquelle und alle bereits in R1/R2 gebundenen
   Ursprungsevents dieses Refundevents; bei neuer Auswahl zusätzlich sämtliche
   gewählten Ursprünge über ihre versionierten Entry-/Line-FKs.
2. Für ein positives CashEvent alle historisch zu ihm gespeicherten C2-
   access_segments_json-Bindungen, einschließlich Gruppen ohne konsumierte
   Linie. Keine heutigen aktiven Rechnungsköpfe als Ersatz.
3. Für einen Abschnitt seine Vorgänger und seine tatsächlichen R1-/R2-
   Releaseclaims; daraus die ganzen Refundevents und wiederum deren volle
   aktuellen Ursprungsumfänge.

Alle erreichten CashEvents werden frisch über die vorhandenen vollständigen
Payment-/Receipt-Quellrechte geprüft. Keine rekursiven öffentlichen
R2._access↔C2._access-Aufrufe. Gültige Eventkreise können durch später ergänzte
Portionbindungen und gemeinsame Einnahmen-Events entstehen; die visited-Menge
beendet die Hülle, während die Eintragsbeweise separat chronologisch geprüft
werden. Die Hülle bleibt rein relational bis zur Autorisierung.

Diese erweiterte aktuelle Refundhülle gilt bei installiertem R2 auch für
R1-Ansichten/Replays und für C2-Zugriffe über gespeicherte R1-/R2-Releasequellen.
Alte Antwortbytes ändern sich dadurch nicht. Fehlt ein historisch nötiger
Zugriff, bleibt der gesamte betroffene Ereignisstand verborgen. Neue
unauthorisierte Ursprungskandidaten werden vollständig ausgelassen.

Globale R1/R2-Lotansprüche und Handoffmengen werden intern ohne Akteurfilter
geprüft. Ein nur zur globalen Rest-/Writerprüfung beitragender fremder Claim
ist keine zusätzliche offengelegte Quelle: öffentlich nur Aggregate und opake
Hashes, keine fremden Refund-/Actor-/Request-IDs, Gründe oder hidden_count.
Die tatsächliche C2-Freigabe einer Rücknahmelinie verlangt hingegen volle
aktuelle Rechte auf deren ganze Refund-/Originhülle.

## HTTP und feste Datenformen

Basis `/api/v1/business/accounting/refunds/v2/events/{event_id}`.
event_id bezeichnet den CashEvent. 32 Kleinhexzeichen für IDs/Requests,
64 Kleinhexzeichen für Hashes, portion_id und group_id. Neue positive Beträge
als kanonische Strings bis 999999999.99; Ausgaben dürfen 0.00 sein. Archivwerte
und kumulative Vergleiche mit Integercents/BigInt, keine Floatkonvertierung.
reason einzeilig, nicht leer, 1–1000 Zeichen. CashDates ISO-Kalendertage,
Erstellzeitpunkte UTC-ISO. Unbekannte Felder, doppelte Queryparameter,
GET-Bodies und sämtliche POST-Queryparameter werden abgewiesen.

| Methode/Pfad | Ergebnis |
| --- | --- |
| GET Basis | State, 200 |
| GET /portions?limit=50&offset=0 | In R1 und R2 noch ungebundene ganze Portionen, 200 |
| GET /origins?portion_id=<hash>&limit=50&offset=0 | Autorisierte passende C1/C2-Lots für R2, 200 |
| GET /history?limit=50&offset=0 | Nur eigene R2-Entries, 200 |
| POST /preview | Nebenwirkungsfreie Vorschau, 200 |
| POST /confirm | Entry, 201, auch bei identischem Replay |

Listen exakt `{items,total,next_offset,scope:'authorized_sources'}`. Limit 1–100,
Default 50; Offset 0–100000, Default 0. Portions nach portion_id; Origins nach
cash_date,origin_event_id,origin_version,entry_id,group_id; History nach eigener
revision DESC,id. total zählt nur autorisierte Einträge. Keine weiteren Filter.

Gemeinsame Flags: `capacity_released:false,scope:'authorized_sources',
tax_status:'unconfigured',tax_result_available:false`. Die erste Angabe besagt,
dass dieser Refundschritt selbst keine Kapazität freigibt, auch wenn C2 später
einen gesonderten Übernahmenachweis erzeugt.

State exakt:

```text
{event_id,source_hash,revision,state_hash,source_kind,amount,currency,
 cash_date,evidence_reference,reference,origin_documented_amount,
 origin_unresolved_amount,unallocated_amount,eligible,blocked_reason,
 writes_allowed,capacity_released,scope,tax_status,tax_result_available}
```

revision zählt ausschließlich R2-Entries des Events. origin_documented_amount
summiert ganze R1+R2-Portionen; origin_unresolved_amount = amount minus diese
Summe und enthält unzugeordnete/unsupported Beträge. unallocated_amount ist
derselbe ursprüngliche Finance-Rest, nicht erneut zu addieren. Andere Quellen
bleiben unter ihrem source_kind lesbar, sind not_customer_refund und haben
keine auswählbaren Refundportionen.

eligible bezeichnet mindestens eine zulässige ungebundene Portion, einschließlich
bind_legacy; es verspricht keine ausreichenden sichtbaren Ursprungslots.
writes_allowed beschreibt Grundrechte/Betriebsgates und bereits gebundene
Quellumfänge, nicht aktuelle Lotreste oder heutige Kandidateneligibilität.

Portion exakt:

```text
{portion_id,kind:'original_refund_allocation',event_id,document_id,
 customer_id,project_id,number,party_name,amount,currency:'EUR',
 payload_sha256,pdf_sha256,capacity_ownership_id,ownership_id,writer,action,
 portion_state_hash,eligible,blocked_reason}
```

capacity_ownership_id ist document_id bei vorhandenem gültigem C2-Handoff,
sonst null. ownership_id ist document_id bei R2-Handoff, sonst null. Writer/
Action sind fest:

| Zustand | writer | action |
| --- | --- | --- |
| Kein C2-Handoff, Quelle sonst gültig | r1 | bind_legacy |
| C2-Handoff, noch kein R2-Handoff, Quelle gültig | r2 | takeover_and_bind |
| R2-Handoff, Quelle gültig | r2 | bind_current |
| Fachlich gesperrte Quelle | entsprechend vorhandener Besitzgrenze | null |

Bis zur tatsächlichen ersten R2-Bestätigung bleibt R1 technisch schreibberechtigt.
Der neue Client bietet für eine bereits in C2 übernommene Rechnung die neue
R2-Aktion an. Nicht gebundene unsupported Portionen bleiben sichtbar; über R1
oder R2 bereits gebundene Portionen fehlen aus der Auswahl.

Origin exakt, R1-Form plus origin_version:

```text
{origin_version,entry_id,group_id,origin_event_id,component_sequence,
 rate,category,tax_reason,document_id,customer_id,project_id,
 number,party_name,cash_date,evidence_reference,reference,currency:'EUR',
 amount,net,tax,returned_amount,returned_net,returned_tax,
 remaining_amount,remaining_net,remaining_tax,lot_state_hash}
```

component_sequence ist die Sequenz des jeweils bezeichneten C1- oder C2-Moduls;
sie ist allein keine globale Lotidentität. amount/net/tax sind die feste
Original-Lotlinie. returned_* umfassen R1+R2 für C1, nur R2 für C2. remaining_*
sind genaue ursprüngliche Cents minus globale Rücknahme. Nur positive Restlots
derselben Rechnung/Kundenbindung mit zulässigem CashDate und vollständigen
Schreib-/Leserechten werden angeboten. Keine automatische Vorauswahl.

Origins auf fehlende/bereits gebundene Portion: 409. Vorhandene fachlich
gesperrte Portion: leere Liste. Für writer r1: 409 legacy_writer_required;
der Client lädt den unveränderten R1-State, dessen Portion und R1-Origins.
Neue R2-Hashes/Versionsfelder werden niemals an R1 geschickt oder rückübersetzt.

Vorschaubody exakt:

```text
{source_hash,expected_revision,state_hash,portion_id,portion_state_hash,
 action,origins:[{origin_version,entry_id,group_id,lot_state_hash,amount}],reason}
```

action ausschließlich takeover_and_bind oder bind_current. 1–500 eindeutige
versionierte Lottripel, positive Beträge, Summe exakt ganze Portion. Antworten
sortieren Linien nach origin_version,entry_id,group_id; ursprüngliche
Arrayreihenfolge bleibt Teil der Requestquittung. Confirm zusätzlich exakt
`{request_id,preview_hash,confirmation:true}`.

Line exakt, R1-Form plus origin_version:

```text
{origin_version,entry_id,group_id,origin_event_id,component_sequence,
 rate,category,tax_reason,origin_cash_date,origin_evidence_reference,
 origin_reference,lot_state_hash,amount,net,tax,
 gross_before,gross_after,net_before,net_after,tax_before,tax_after,
 remaining_gross,remaining_net,remaining_tax}
```

entry_id/group_id bezeichnen den Ursprung, nicht den neuen R2-Entry.
before/after sind die vollständige kumulative Rücknahme dieses versionierten
Lots. amount/net/tax sind ausschließlich die neue positive Rücknahmedifferenz.

Preview exakt, R1-Form plus action und neue Portion:

```text
{event_id,source_hash,expected_revision,state_hash,action,cash_date,
 evidence_reference,reference,portion:Portion,amount,net,tax,lines,reason,
 preview_hash,capacity_released,scope,tax_status,tax_result_available}
```

preview_hash ist SHA-256 über die vollständige kanonische Vorschau ohne dieses
Feld. Entry ist Preview ohne expected_revision,state_hash, dafür
`{id,sequence,revision,previous_state_hash,created_by,created_at}`.
sequence ist die eigene positive globale R2-Sequenz. Alle gespeicherten DTOs
bleiben ihre damalige vollständige Antwort, einschließlich ihrer Vorschauportion.

## Zustandsbindung, Proofs und Referenzen

state_hash bindet unveränderte vollständige Refundquelle/Portionsmenge,
R1- und R2-Eintragsköpfe des Events sowie die C2-/R2-Handoffs seiner Rechnungen.
portion_state_hash bindet zusätzlich exakte Allocation/Archive/Kundenbindung,
Writeraktion, vollständige damalige R1-Rechnungsclaims und beobachtete globale
C1-, R1- und C2-Sequenzköpfe. lot_state_hash bindet versionierten unveränderten
Lot-/Quellbeweis und sämtliche früheren R1/R2-Claims dieses Lots. Die Hashes
dürfen globalen fremden Verbrauch binden, geben dessen Identitäten aber nicht aus.
Globale Beobachtungsgrenzen können auch Vorschauen anderer Rechnungen veralten
lassen. Historische erfolgreiche Replays verwenden keine heutigen Resthashes.

OriginReference exakt:

```text
{origin_version,entry_id,group_id,origin_event_id,entry_sha256,
 proof_sha256,line_sha256,source_hash}
```

ReturnReference exakt, für gemeinsame neue Proofs:

```text
{refund_version,refund_entry_id,origin_version,origin_entry_id,group_id,
 refund_event_id,origin_event_id,sequence,entry_sha256,proof_sha256,
 line_sha256,cash_date,net,tax,amount}
```

refund_version r1/r2 bestimmt die Rücknahmetabelle und die Bedeutung sequence.
R1-Referenzen werden nur im neuen Schema um die festen Versionen r1/c1 ergänzt;
ihre alten gespeicherten Referenz-JSONs werden nicht verändert. Referenzlisten
kanonisch nach refund_version,sequence,refund_entry_id,origin_version,
origin_entry_id,group_id. Alle Geld-/Quelle-/Beziehungsnachweise vollständig
prüfen; ein gültiger gespeicherter Hash allein genügt nicht.

R2-Proofschema 1 exakt:

```text
{schema_version:1,
 source:{event_sha256,portion:<vollständige ursprüngliche Refundportion>},
 c1_sequence,r1_sequence,c2_sequence,
 capacity_handoff:{document_id,entry_id,handoff_sha256},
 refund_handoff_before:null|{document_id,entry_id,handoff_sha256},
 legacy_claims:[ReturnReference],
 origins:[OriginReference],
 claims_before:[{origin_version,entry_id,group_id,claims:[ReturnReference]}]}
```

legacy_claims sind alle R1-Linien der Rechnung am beobachteten R1-Präfix;
bei bestehendem R2-Handoff exakt dessen eingefrorene Menge. origins und
claims_before entsprechen vollständig der sortierten neuen Linienauswahl.
c2_sequence ist der exakt zuvor vorhandene **globale** C2-Kopf, nicht ein
Rechnungs- oder Eventfilter. C2-Handoff und gewählte C2-Lots müssen bereits
im geprüften gemeinsamen Präfix vorhanden sein. Ein erst späterer heutiger
DB-Datensatz genügt nicht. R1/C1-Beobachtungsgrenzen sind ebenfalls globale
strikte Integer und begrenzen die rekonstruierten ursprünglichen Quellen.

Neue C2-Entries verwenden bei installiertem R2 intern Proofschema 2, auch wenn
noch kein R2-Entry existiert. Das Schema hat genau die bisherigen C2-Prooffelder
plus r2_sequence:

```text
{schema_version:2,source,portions_before,basis,archive,eligibility,
 c1_sequence,r1_sequence,r2_sequence,legacy,prior_segments,gate,
 authorized_returns,new_segments}
```

r2_sequence ist der exakt vorherige globale R2-Kopf. source/portions_before,
basis/archive/eligibility, legacy und prior_segments behalten ihre fachliche
C2-Bedeutung. authorized_returns ist eine sortierte eindeutige Liste ganzer
autorisierter Refund-CashEvent-IDs beider Versionen, ohne öffentliche Ausgabe.
Neue Segmentbeweise erhalten schema_version:2 und ansonsten dieselben Felder
document_id,group_id,revision,previous_id,basis,carry,returns,not_before_date,id;
returns enthält ReturnReference. id ist weiterhin SHA-256 über den kanonischen
vollständigen Abschnitt ohne id. carry und Datumsgrenze folgen unverändert C2.

gate hat weiterhin exakt refunds und complete. Jede Refundbeobachtung erhält
im neuen Schema genau ein zusätzliches refund_version-Feld:

```text
{allocation,source_hash,event_id,refund_version,refund_entry_id,
 refund_entry_sha256}
```

refund_version/Entry/Hash sind null ohne Bindung, sonst r1 oder r2 und exakt
die ganze gültige Bindung. Mehrfachbindung ist ein Integritätsfehler. Ein
beobachteter R2-Entry darf nicht hinter r2_sequence liegen. Vollständigkeit
bezieht sich auf alle vorhandenen Finance-Refund-Allocations der Rechnung,
auch vor E1a-Import. Später angelegte Refunds werden nicht rückwirkend in alte
Beobachtungen hineingelesen.

**C2-Proofschema 1 bleibt exakt erhalten:** kein r2_sequence-Feld, keine neuen
Versionsfelder in seinen Return-/Gate-/Segmentbeweisen, unveränderte IDs,
Formeln und gespeicherte Zugriffsliste. Der historische Adapter verwendet
seinen alten R1-Datenraum. Neue normalisierte Referenzen dürfen nicht in den
expectedProof eines alten Entries gelangen. Öffentliche C2-Pfade, Eingaben,
State/Portion/Group/Preview/Line/Entry-DTOs bleiben unverändert.

## Gemeinsamer Validator und Reihenfolge

`accounting_joint_ledger` prüft C1/R1 unverändert als Quellen und verarbeitet
C2/R2 in einem einzigen nichtrekursiven gemeinsamen Durchgang. Es ruft weder
wechselseitig vollständige Domänen-_ledger-Funktionen noch Restorehorizonte
auf. Es liefert getrennte geprüfte Teilzustände für aktuelle DTOs, Lotreste,
Claims, Handoffs, Abschnitte und eigene Tabellenzählungen.

`accounting_joint_order.merge_observed_heads` ordnet die vollständigen globalen
C2- und R2-Ströme. Eigene Sequenzen strikt 1..N, Gegenköpfe strikt Integer ab 0,
innerhalb der Länge des Gegenstroms und monoton; bool wird abgewiesen. Alte
C2-Proofschema-1-Entries erhalten ausschließlich im Adapter den virtuellen
R2-Kopf 0. Schema 1 ist ein zusammenhängender Präfix, nach Schema 2 unzulässig.

Ein beobachteter Kopf k bedeutet nach Gegeneintrag k und vor k+1. Je Schritt
muss genau einer der nächsten Einträge seinen beobachteten Gegenkopf gleich
dem geprüften Gegencursor haben. Zwei erlaubte Kandidaten sind eine unmögliche
gegenseitige Vorherbehauptung; keiner bedeutet fehlenden/zukünftigen/veralteten
oder zyklischen Bezug. Bloßes topologisches Sortieren früherer Verweise wäre
falsch. Erst den Eintrag vollständig fachlich validieren, dann seinen Cursor
und die eigenen Lot-/Claim-/Abschnittsstände anwenden.

Die beobachteten globalen c1_sequence- und r1_sequence-Grenzen dürfen auch
über den gesamten gemischten C2/R2-Durchgang nicht zurücklaufen. Jede Grenze
muss im vollständigen jeweiligen Quellstrom existieren. Ein nach bereits
beobachtetem neuerem R1-Stand behaupteter älterer Gate-/Claimstand ist ungültig;
die Grenzen ersetzen nicht die vollständige Prüfung der tatsächlichen Quellen.

Ein R2-Schritt sieht ausschließlich C2-Lots/Handoffs aus diesem geprüften
Präfix. Ein neuer C2-Schritt sieht ausschließlich frühere R2-Returns. Vorstände,
ganze Portionen, exakte Überträge, Requests und relationale Zeilen werden
gegen die tatsächlichen bisherigen Zeilen rekonstruiert; konsistent neu
berechnete JSON-Hashes allein können keinen erfundenen Vorbetrag legitimieren.
Keine neue Startgrenztabelle, Zeitstempelreihenfolge oder zweite positive Route.

## Fünf additive Tabellen

Genau folgende Tabellen; alte Modul-DDL und Guards bleiben unverändert:

1. `business_accounting_refunds_v2_handoffs`: document_id PK/FK zur Rechnung;
   entry_id UNIQUE FK zum ersten R2-Entry; handoff_json/handoff_sha256.
   Handoff-JSON exakt `{document_id,entry_id,capacity_handoff,r1_sequence,
   legacy_claims,created_by,created_at}`. Die alten R1-Claims werden nicht kopiert
   oder neu gebucht, sondern als vollständige flache Beweismenge gebunden.
2. `business_accounting_refunds_v2_entries`: id PK, sequence UNIQUE >0,
   event_id FK zum CashEvent, revision >0 mit UNIQUE(event_id,revision),
   document_id FK, refund_allocation_id UNIQUE FK zur alten Allocation,
   portion_id UNIQUE, source_hash, previous_state_hash, entry_json/entry_sha256,
   proof_json, access_origins_json TEXT NOT NULL, created_by/created_at.
3. `business_accounting_refunds_v2_lines`: entry_id FK zum neuen Entry,
   origin_version CHECK c1/c2, origin_entry_id, group_id;
   PK(entry_id,origin_version,origin_entry_id,group_id). Dazu nullable
   origin_c1_entry_id und origin_c2_entry_id mit CHECK genau des passenden
   nichtnullen Zweigs (`IS NOT NULL` ausdrücklich, wegen SQL-NULL-Logik) und
   Gleichheit zu origin_entry_id; zusammengesetzte
   FKs `(origin_c1_entry_id,group_id)` auf C1-lines und
   `(origin_c2_entry_id,group_id)` auf C2-capacity-lines. Alle festen Line-
   Geldfelder amount/net/tax, before/after und remaining_* plus origin_line_sha256.
4. `business_accounting_refunds_v2_requests`: PK(user_id,request_id), event_id,
   request_json/request_hash, entry_id UNIQUE FK zum R2-Entry. Requesthash über
   kanonisches `['refunds_v2.confirm',event_id,<ganzer ursprünglicher Body>]`.
5. `business_accounting_refunds_v2_releases`: PK(refund_entry_id,origin_version,
   origin_entry_id,group_id), zusammengesetzter FK auf die entsprechende R2-
   Linie; segment_id FK zur bestehenden C2-Segmenttabelle,
   reference_json/reference_sha256 mit der vollständigen ReturnReference.

access_origins_json ist exakt die kanonische sortierte eindeutige Liste
`[{origin_version,entry_id,group_id}]` aller tatsächlich gewählten Originlinien.
Sie wird vor Fachdetails in relationale Quell-IDs aufgelöst und exakt gegen
Linien/Proof geprüft. Globale bloße Restansprüche werden nicht zu gewählten
Ursprüngen erklärt. Zusätzliche aktuelle Bindungen desselben ganzen Refund-
oder positiven Events werden durch die relationale Hülle mitgeprüft.

Bestehende C2 access_segments_json enthält weiterhin alle prior/new-Segmente,
auch unbenutzte Gruppen. Beim Auflösen werden beide Releaseclaimtabellen
gelesen. R1-Returns schreiben ausschließlich in die alte
business_accounting_capacity_releases; R2-Returns ausschließlich in die neue
R2-releases. Keine Änderung des alten R1-Fremdschlüssels. Beide Claimräume
werden über versionierte Identität auf Einmaligkeit und vollständige Zeilen-
zuordnung geprüft. Jeder Teilhorizont zählt nur seine eigenen Tabellen.

Entry, Linien, erster Handoff, Quittung und Audit entstehen in derselben
SQLite-IMMEDIATE-/PG-Advisory-Transaktion. Neue C2-Segmente und beide Arten
Releaseclaims entstehen atomar mit ihrer positiven C2-Bestätigung. Preview und
GET schreiben nichts. Alle neuen Tabellen erhalten UPDATE-/DELETE-Schutz,
SQLite zusätzlich REPLACE-Konfliktschutz, PG Runtime ausschließlich SELECT/INSERT.
Jeder Teilfehler rollt sämtliche Wirkungen des Befehls zurück.

## Idempotenz, Marker und Clientverhalten

Confirmfolge für R2 und die ergänzte R1-Route: vollständige frische Quellenhülle,
Schreib-/Betriebsgates, gemeinsame historische Integrität, Lookup der eigenen
ursprünglichen Protokollquittung. Exakter Treffer liefert unveränderten Entry.
Geänderter Body/Event unter derselben Benutzer-/Request-ID liefert unmarkierten
409. Erst bei fehlender Quittung aktuelle Writerzuständigkeit, Kandidaten,
Lotstände, Vorschau und gegebenenfalls Handoff prüfen. Der heutige positive
C2-Financegatezustand darf keinen gültigen historischen Refund-Replay sperren.

Nur ein sicher unangenommener aktueller Vorbereitungskonflikt nach diesem
fehlenden Receiptlookup, vor Insert/Audit, darf liefern:

```text
HTTP 409
{error:<Konflikttext>,request_resolution:'not_accepted'}
```

Rechte-/Modus-/Restore-/Runtime-/Integritätsfehler vor Lookup tragen keinen
Marker. Keine Textauswertung und keine Verschiebung der Sicherheitsgates.
Andere Request-ID oder Nutzer umgehen weder Refundportion noch Lotgrenze.

Beide Clients verwenden für R1/R2 einen gemeinsamen logischen Refund-Eventkey
und behalten gespeicherten Pfad, ganzen Body, Versionsangaben und Request-ID
unverändert. Neues R2-Pending wird stets neutral angezeigt. Preflight liest
den gespeicherten Writer-State frisch; danach identischer Confirm. Keine
heutige Kandidateneligibilität als Replayvoraussetzung, kein automatischer
Versionswechsel. Die serverseitige Quellenhülle wird nicht im Client rekursiv
nachgebaut.

Die bestehende eng begrenzte Pendingregel wird auf beide Refund-Confirmpfade
erweitert: unmarkierte 409, 403/404/423, 5xx und Netzfehler bleiben offen;
Erfolg oder exakt markierter 409 lösen den unklaren Auftrag auf. Andere
Operationen unverändert. 401/Sitzungswechsel behalten Identitätsschutz.
Generationswechsel während eines Retries erzeugt keinen lokal terminalen 409.

Vor Wiederanzeige zwischengespeicherter Originwahl aus früheren Listenseiten
werden der R2-Refund-State und je betroffenem positivem origin_event_id der
vorhandene C2-State frisch gelesen. Dessen serverseitige Hülle gilt auch für
C1-Lots. Im Auswahlkontext writes_allowed prüfen, nicht eligible oder aktuelle
positive Aufteilbarkeit. Bei fehlendem Zugriff alte Details verbergen.
Pending bleibt unabhängig davon neutral. Keine neue Autorisierungsroute.

Aktuelle Originlisten und Eingaben verwenden immer die volle Versionsidentität.
Die Oberfläche unterscheidet ursprüngliche Aufteilungen und Aufteilungen nach
Wiederverwendung verständlich, ohne rohe IDs. Der bisherige C2-Hinweis auf nicht
unterstützte neue Erstattungsursprünge entfällt nur bei tatsächlich verfügbarem
R2-Modul plus Feature. Quellen bleiben vorhandene echte Refunds; keine neue
Refund-Erfassungsoberfläche in diesem Schritt.

## Fehler und Teilinstallation

400: unbekannte/fehlende Felder, Typen/Versionen, doppelte versionierte Lots,
ungültige Cents/Begründung/Bestätigung oder nicht exakte Portionssumme.
403/404: fehlende aktuelle Rechte/Quellen ohne Fremddetails. 409: Writer-/
Quelle-/Archiv-/Cent-/Datum-/Hash-/Revision-/Requestkonflikt oder beschädigte
Historie/Teilinstallation. 423: deaktiviertes Finanzmodul. 405: falsche Methode.
Ungültige gespeicherte JSON-/Cent-/Sequenzwerte werden zu 409 normalisiert.

Öffentliche blocked_reason: not_customer_refund, source_customer_unresolved,
unsupported_document, unallocated, fully_documented; sonst null. Direkte
R2-Vorbereitung einer legacy-Portion liefert 409 legacy_writer_required;
sie ist im konsolidierten State weiterhin eine zulässige bind_legacy-Aktion.
Leere sichtbare Originlisten behaupten keine ausreichende Kapazität und geben
keine Anzahl verborgener Quellen aus.

Das Modul gilt nur dann als nicht installiert, wenn alle fünf Tabellen und
sein Migrationsmarker fehlen und kein C2-Proofschema 2/R2-Verweis existiert.
Jede Teilinstallation, fehlende Abhängigkeit oder unlesbare Besitzergrenze
scheitert geschlossen. Kein stiller Rückfall auf R1 oder C2-Proofschema 1.
Neue C2-Entries verwenden bei installierter Erweiterung immer Schema 2;
deaktivierte Sichtbarkeit des neuen Features ändert keine persistente
Writerzuständigkeit oder bereits gebundene historische Quellen.

## H6, Berichtschema 7 und unveränderte Finanzprojektionen

Eigener R2-Teilhorizont exakt:

```text
{schema_version:1,
 table_counts:{business_accounting_refunds_v2_handoffs:<count>,
               business_accounting_refunds_v2_entries:<count>,
               business_accounting_refunds_v2_lines:<count>,
               business_accounting_refunds_v2_requests:<count>,
               business_accounting_refunds_v2_releases:<count>},
 sha256}
```

Hash über alle vollständig geprüften eigenen Zeilen einschließlich Requests
und R2-Releaseclaims, deterministisch sortiert. Vollständige Abwesenheit ergibt
null; Teilinstallation/kaputte Historie einen Fehler. Kein DDL, Commit oder
Migration im Hook/Inspect. Gemeinsamer H6 exakt:

```text
{schema_version:6,prejournal:<H1>,allocations:<A1>,components:<C1>,
 refunds:<R1>,capacity:<K1>,refunds_v2:<R2>}
```

Neue Betreiberfreigaben verlangen Berichtschema 7 auch bei leerem R2-Modul.
Übrige äußere Felder bleiben exakt schema,restore_id,reviewed_by,reviewed_at,
number_horizons,outbound_reconciled,accounting_horizon,accounting_reconciled,
accounting_external_review; dessen Felder bleiben reviewed_since_backup,
evidence_sha256,note. Alle unabhängigen Betreiber-/Stillstands-/Restore-ID-
Prüfungen gelten unverändert.

H1/A1/C1/R1/K1 behalten ihre festen Tabellenmengen; alte gespeicherte Zeilen
bleiben unverändert. Historisches H5/Berichtschema 6 erhält kein nachträgliches
refunds_v2-Feld. Bereits erfolgreiche alte identische Betreiberquittungen sind
nur bei bereits aufgehobener Sperre wirkungslos replaybar; sie entsperren keinen
neuen Restore. Die nächste Freigabe benötigt den vollständigen aktuellen H6.

Finance-Payments, Original-Allocations, CashEvents, OP/Mahnung, Bankdaten,
gespeicherte Exporte und alte Antworten erhalten keine zusätzliche Wirkung.
Die neuen Ansichten zeigen eine dokumentarische Quellen-/Rücknahmebindung,
keine steuerliche Einordnung oder vollständige Unternehmens-/Jahresabnahme.

## Erforderliche gezielte Nachweise

Noch auszuführen und separat an den tatsächlichen Quellstand zu binden:

1. Genannter gemischter 26,44-Fall exakt 22,21/4,23; voller C1-Lot über
   R1+R2 ohne Reset. Weitere C2-Wiederbelegung und mindestens zwei neue R2/C2-
   Zyklen mit exakt erhaltenen N/T/G-Cents.
2. Ganzer Refundanteil global einmal, Mischportion atomar; konkurrierendes
   R1/R2-Handoff, letzter Lotrest und doppelte R2-Releaseclaims über echte
   getrennte PG-Verbindungen. Fehler nach Linie/Handoff/Audit ohne Teilwirkung.
3. Alter C2-v1-Adapter liefert exakt alte Proofs/Antworten/IDs/Quittungen;
   globale beobachtete Gegenköpfe und echte Präfixexistenz, keine spätere DB-
   Quelle als vermeintlicher früherer Ursprung. Gefälschte Zyklen/Vorstände
   trotz konsistent erneuerter JSON-Hashes abweisen.
4. Vollständige aktuelle Quellenhülle, unbenutzte historische Gruppen,
   spätere Projekt-/Origin-Erweiterung, Rechteentzug und gültiger Eventkreis;
   keine Details vor Autorisierung, kein rekursiver Endlosaufruf.
5. Alte erfolgreiche R1/C2/R2-Replays vor heutiger Writersperre/Kandidatengate;
   veränderte Requests unmarkiert; No-Receipt-Konflikte korrekt markiert;
   Rechte-/Restorewechsel zwischen Preflight und Retry erhalten Pending.
6. Unknown Finance-Refund vor Import sperrt zusätzliche C2-Freigabe, nicht
   seine eigene R2-Klärung. CashDates, spätere Stornierung, nicht leere und
   leere Überträge, per-portion gemischte Writer und globale Beträge prüfen.
7. SQLite-/PG-Guards, partielle Module, alte und neue Horizonte sowie echte
   Restore-/Schema-7-Freigabe. Alte Schema-6-Quittung entsperrt keinen Restore.
8. Browser/Flutter über echte API: spätere synthetische Finance-Refundquellen
   erst im jeweiligen Zyklus per authentifiziertem Produkt-POST erzeugen;
   neue Import-/R1-/R2-/C2-Aktionen über UI. Quelle per API ausdrücklich als
   Testaufbau dokumentieren, keine vorab gesäten künftigen Gateblocker und
   keine nachgebauten Antwort-Dummys. Keine neue Finance-Erfassungsoberfläche.
