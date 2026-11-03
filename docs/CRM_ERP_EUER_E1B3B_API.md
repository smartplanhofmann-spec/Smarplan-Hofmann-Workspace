# E1b-3b: genaue Restkapazitäten – Implementierungsvertrag

Stand: 03.11.2026. Basis: E1b-3a-Commit `ec69d13`.
Dieser Abschnitt ist im beschriebenen Umfang implementiert. Tatsächlich
ausgeführte Prüfungen und ausstehende Nachweise stehen im
[Fortschritt](CRM_ERP_FORTSCHRITT.md) und im
[Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_E1B3B.json); eine Gesamtabnahme wird daraus
nicht abgeleitet. Der [Entwurf](CRM_ERP_EUER_E1B3B_ENTWURF.md)
erklärt die Entscheidungen. Bei Abweichungen gelten die genauen Festlegungen
dieser Datei. E1b-2/C1 und E1b-3a/R1 bleiben historische eigene Protokolle.

## Modul und begrenzter Umfang

Modul `business_accounting_capacity`, Feature
`accounting_document_component_reuse`, Klasse
`ReusableDocumentComponents(office,clock=None)`. Abhängigkeiten: E1a, E1b-1,
E1b-2 und E1b-3a vollständig installiert. Bestehendes Finanzmodul und bestehende
Capabilities bleiben erhalten; das neue Feature ist additiv.

Unterstützt sind ganze ursprüngliche oder zusätzliche Einnahmenportionen
normaler positiver finaler EUR-Ausgangsrechnungen. Supplier-Payouts bleiben C1.
Eine Rechnung wechselt einmalig und atomar mit **allen** archivierten Gruppen
von C1 zum neuen Schreiber C2. Die erste Übernahme verlangt mindestens eine
gültige noch nicht übernommene R1-Rücknahmelinie und eine gleichzeitig bestätigte
erste ganze C2-Einnahmenportion. Keine isolierte Freigabe, keine Vorreservierung
und kein Schreiben durch GET oder Vorschau.

Vor Übernahme darf C1 neue positive Portionen dieser Rechnung dokumentieren.
Danach darf C1 nur bestehende erfolgreiche Bestätigungen identisch wiederholen.
Andere Rechnungen und Supplier-Payouts bleiben unabhängig C1-schreibbar. Ein
CashEvent kann deshalb Portionen mit unterschiedlichen aktuellen Schreibern
enthalten. Die Schreiberentscheidung erfolgt je ganzer Portion/Rechnung.

R1 bleibt einziger Rücknahmeschreiber für C1-Lots. Neue C2-Lots können in diesem
Schritt noch nicht als Refundursprung verwendet werden. Auch eine ganze
Refundportion, die C1- und C2-Lots benötigt, bleibt ungeklärt; keine Teilbindung.
Weitere Refundversionen sind ausdrücklich Folgearbeit. Keine Steuerbuchung,
keine steuerliche Periode und keine vollständige EÜR.

## Quellenrechte und Gates

Lesen verlangt global `accounting.read`, global `finance.read` und vollständige
aktuelle Rechte auf den ganzen Einnahmen-CashEvent. Ursprünglich private
Geldflüsse bleiben privat. Bestehende C2-Einträge verlangen außerdem vollen
aktuellen Lesezugriff auf sämtliche in ihren Beweisen tatsächlich gebundenen
R1-Refundevents und deren C1-Origin-Events, einschließlich weitergetragener
Abschnittsquellen. Fehlt ein erforderlicher historischer Zugriff, wird der
ganze Ereignisstand verborgen, ohne Teilantwort oder versteckte Anzahl.
Das umfasst auch eine in der gespeicherten Portion/ihrem Beweis enthaltene
Gruppe, aus der dieser Entry keine positive Linie verbraucht hat. Maßgeblich
ist die vollständige damalige Abschnittsbindung, nicht nur die konsumierte
Gruppenauswahl und nicht die heutige Menge aktiver Abschnitte.

Vorschau/Bestätigung verlangen zusätzlich global `accounting.prepare`, global
`finance.write`, vollständige Quellschreibrechte und aktuelle Schreib-/Leserechte
auf sämtliche tatsächlich verwendeten Rücknahme-/Ursprungsquellen. Diese Rechte
werden vor deren Details/Beweisen und vor historischem Replay geprüft. Bloßer
Rechnungszugriff ersetzt die vollständigen Refund-/Origin-Quellrechte nicht.

Neue Freigaben benötigen zusätzlich vollständige Rechte auf alle neu
beitragenden R1-Refunds und ihre C1-Origins. Fehlende Rechte auf solche neuen
Quellen ergeben neutral `source_access_required`; keine fremden IDs, Namen,
Begründungen oder Anzahlen. Globale C1-Verbräuche bleiben ungefilterte geprüfte
Aggregate und verlangen nicht pauschal Rechte auf jeden fremden C1-Zahler.

Aktiver Businessmodus, Finanzmodul, Restore-/Finanzfreigabe und vorhandene
Runtimeprüfung gelten unverändert. Alle schreibenden Entscheidungen verwenden
dieselbe SQLite-IMMEDIATE-/PG-Advisory-Serialisierung wie C1/R1/Finance.

Das Refundgate liest **alle Finance-Refund-Allocations der konkreten Rechnung**,
auch wenn ihr Refund noch nicht nach E1a übernommen wurde. Jede ganze Allocation
muss einen gültigen E1a-Refund und eine gültige ganze R1-Bindung haben. Sonst
`refund_origin_unresolved`. Kein Akteurfilter für diesen Test. Unzugeordnete
Refundreste werden keiner Rechnung geraten zugeordnet und erzeugen keine
Kapazität; der lokale Abgleich behauptet keine vollständige Unternehmensklärung.

Bei ungeklärtem Gate bleibt vor Übernahme die bisher mögliche C1-Dokumentation
erlaubt, damit fehlende C1-Ursprünge für R1 entstehen können. Nach Übernahme
bleibt bereits bestätigte aktuelle C2-Restkapazität benutzbar; zusätzliche
Rücknahmecents bleiben pending. Ein späterer ungeklärter Refund entzieht keine
früher korrekt übernommene Kapazität und schaltet die Rechnung niemals auf C1
zurück. Ein Betrag, der nur unter Nutzung pending Cents passt, bleibt gesperrt.

## Restabschnitte und Zeitregel

N/T/G sind stets ganze nichtnegative Cents mit G=N+T. Die archivierte
`group_id` bleibt unverändert; jeder neue Abschnitt erhält eigene Identität.

Erstübernahme je Gruppe:

```text
carry = archived_group - sum(all_valid_C1_lines)
new_basis = carry + sum(newly_claimed_R1_lines)
```

Beide Operationen erfolgen getrennt und exakt für N/T/G. R1 liefert die
tatsächlich eingefrorenen Rücknahmecents seiner konkreten Lots, keine erneut
aus dem Rechnungsverhältnis berechneten Werte.

Späterer Nachfolger:

```text
carry = previous_segment_basis - actual_consumed_components
new_basis = carry + sum(newly_claimed_R1_lines)
new_consumed = 0
```

Ohne neue Returns bleibt derselbe Abschnitt bestehen. In einem Abschnitt:

```text
Tax(C) = floor((2*C*T + G) / (2*G))
Net(C) = C - Tax(C)
line_tax = Tax(C+amount) - Tax(C)
line_net = amount - line_tax
0 < amount <= G-C
```

Nullgruppen werden bei der Gesamtübernahme mitbelegt, aber nicht zur positiven
Eingabe angeboten. Kein Reset/Refundabzug in C1 `_pool`, keine Veränderung alter
C1/R1-Linien und keine Wiederverwendung einer schon übernommenen R1-Linie.

`not_before_date` ist das größte CashDate der Returns, deren Cents der
Abschnitt enthält. Beim Übertrag nicht leerer alter Kapazität wird deren
Datumsgrenze konservativ vollständig weitergetragen; keine Aufspaltung nach
vermuteter Centherkunft. Ein leerer Übertrag trägt keine Datumsgrenze weiter.
Jede neue Einnahmenlinie verlangt `receipt.cash_date >= not_before_date` ihres
verwendeten Abschnitts; null bedeutet keine zusätzliche Datumsgrenze.

Die erste Gesamtübernahme verlangt konservativ ein Einnahmendatum mindestens
gleich dem größten Refunddatum **aller** übernommenen Rechnungsgruppen. Ist
das nicht möglich, darf vor Übernahme weiterhin eine passende C1-Portion
innerhalb ihres alten Rests dokumentiert werden. Nach Übernahme bleiben zu
frühe Einnahmen für die betroffenen Abschnitte ungeklärt.

Nach Übernahme werden neue Returns je Gruppe nur dann in einen Nachfolger
übernommen, wenn Gate, vollständige neue Quellrechte und Einnahmendatum passen.
Andernfalls bleiben sie pending und ein ausreichend datierter alter Abschnitt
kann weiter benutzt werden. Eine passende Bestätigung übernimmt alle aktuell
freigabefähigen Gruppen-Nachfolger dieser Rechnung atomar, auch wenn einzelne
dieser Gruppen keine positive Einnahmenlinie erhalten. Der Benutzer sieht
diese Kapazitätsänderungen vollständig in der Vorschau.

## HTTP und allgemeine Datenformen

Basis `/api/v1/business/accounting/components/v2/events/{event_id}`.
Transportversion bleibt `/api/v1`. `event_id` ist die 32-kleinhexige CashEvent-ID.
IDs sind 32 Kleinhexzeichen, Hashes/portion_id/group_id/segment_id 64 Kleinhex.
`ownership_id` ist die stabile Rechnungs-ID des einmaligen Übernahmedatensatzes,
vor Übernahme null. Kein zufälliger Vorschau-Identifier.

Geldstrings sind kanonisch mit zwei Dezimalstellen. Neue Eingaben/ganze Portion
höchstens `999999999.99`; gespeicherte Archiv-/Gruppenwerte können größer sein.
Clients verwenden BigInt/Strings. Gleiche reason-, Seiten-, Query-, unbekannte-
Felder-, GET-Body- und POST-Query-Regeln wie E1b-2. `reason`: einzeilig, 1–1000
Zeichen. Höchstens 500 eindeutige positive Gruppenbeträge, exakt ganze Portion.

| Methode/Pfad | Ergebnis |
| --- | --- |
| GET Basis | State, 200 |
| GET `/portions?limit=50&offset=0` | Noch undokumentierte ganze Portionen mit Schreiberentscheidung, 200 |
| GET `/history?limit=50&offset=0` | Nur neue C2-Entries, 200 |
| POST `/preview` | Nebenwirkungsfreie neue C2-Vorschau, 200 |
| POST `/confirm` | Neue C2-Bestätigung oder identischer Replay, 201 |

Listen exakt `{items,total,next_offset,scope:'authorized_sources'}`. Portions
nach portion_id; C2-History nach eigener revision DESC,id. Limit 1–100,
Default 50; Offset 0–100000, Default 0. Die C1-Historie bleibt an ihrem alten
Pfad vollständig unverändert und wird vom Client zusätzlich geladen. Keine
Umdeutung alter Entries und keine neue Writerhülle um C1-Antworten.

Gemeinsame Flags in State/Preview/Entry:
`scope:'authorized_sources',tax_status:'unconfigured',tax_result_available:false`.

`Money` exakt `{net,tax,gross}`.

`Capacity` exakt `{segment_id,net,tax,gross,not_before_date}`;
segment_id ist null für noch nicht übernommene C1-Restkapazität. N/T/G meinen
hier die **noch verfügbaren** Cents, nicht den Lebenszeitverbrauch.

`PendingReturns` exakt `{net,tax,gross,not_before_date}`.

`State` exakt:

```text
{event_id,source_hash,revision,state_hash,source_kind,amount,currency,cash_date,
 documented_amount,undocumented_amount,unallocated_amount,
 eligible,blocked_reason,writes_allowed,
 scope,tax_status,tax_result_available}
```

revision zählt nur eigene C2-Entries. state_hash bindet unveränderte Quelle,
vollständige aktuelle Quellenportionen, C1-/C2-Eintragsköpfe und die relevanten
Rechnungsübernahmestände. documented_amount summiert ganze positive C1- und
C2-Portionen; undocumented_amount ist Eventbetrag minus diese Summe. Refunds
werden hiervon nicht abgezogen. source_kind bleibt wie C1. Andere Quellen sind
lesbar mit `not_customer_receipt` und ohne neue C2-Portionen.

writes_allowed beschreibt aktuelle Grundrechte/Betriebsgates, unabhängig davon,
ob eine konkrete neue Aktion möglich ist. eligible bedeutet mindestens eine
aktuell mögliche angebotene Aktion, einschließlich document_legacy.

`Portion` exakt:

```text
{portion_id,kind,event_id,document_id,customer_id,project_id,number,party_name,
 amount,currency,payload_sha256,pdf_sha256,
 ownership_id,writer,action,refund_status,pending_blocked_reason,
 portion_state_hash,eligible,blocked_reason,groups}
```

kind: original_allocation oder additional_allocation. Metadaten aus der
unveränderten Quelle/dem Rechnungsarchiv. writer ist `c1` oder `c2`.
action: `document_legacy`, `takeover_and_document`, `document_current` oder null.
refund_status: `clear`, `unresolved` oder null bei nicht unterstützter Quelle.
pending_blocked_reason: null, refund_origin_unresolved, source_access_required
oder receipt_before_capacity; er darf neben einer möglichen aktuellen Aktion
bestehen. blocked_reason beschreibt dagegen die angebotene ganze Portion.

Ohne Übernahme wird takeover_and_document/writer c2 angeboten, wenn sämtliche
Übernahmevoraussetzungen passen. Andernfalls document_legacy/writer c1, soweit
C1 innerhalb seines alten Rests zulässig ist. Andernfalls action null. Nach
Übernahme ausschließlich document_current/writer c2 oder action null.

portion_state_hash bindet alle archivierten Gruppen, aktuelle Abschnittsköpfe,
vollständige C1-Claims, neue passende R1-Claims, beobachteten Finance-Refundstand,
Datumsgrenzen und die konkrete Entscheidung. Eine konkurrierende Änderung
macht eine neue Vorschau ungültig. Erfolgreiche historische Replays prüfen
diese heutigen Kandidatenstände nicht nochmals.
Die Beweise binden auch globale C1-/R1-Beobachtungsgrenzen. Deshalb kann ein
neuer C1-/R1-Eintrag einer anderen Rechnung ebenfalls eine noch unbestätigte
Vorschau ungültig machen; erneut laden und prüfen. Historische Entries und
identische erfolgreiche Replays bleiben davon unverändert.

`Group` exakt:

```text
{group_id,rate,category,reason,archive:Money,
 current_capacity:Capacity,pending_returns:PendingReturns,
 offered_capacity:Capacity,transition,group_state_hash}
```

archive sind die unveränderten Originalwerte. transition: none, takeover oder
successor. offered_capacity ist die nach geltenden Gates tatsächlich für
diesen Befehl angebotene Kapazität; bei gesperrten neuen Returns kann sie
current_capacity entsprechen. Ein zu spätes current_capacity bleibt sichtbar,
ist für dieses Einnahmendatum jedoch nicht verwendbar. Die Gruppensumme für
eligible berücksichtigt nur datumszulässige angebotene Kapazitäten.

Für document_legacy dienen die Werte als C1-Übersicht. Der Client lädt vor der
alten Vorschau zusätzlich den unveränderten C1-State und die konkrete alte
C1-Portion und verwendet deren Revision/Hashes; kein C2-State an C1 senden.

Vorschaubody exakt:

```text
{source_hash,expected_revision,state_hash,portion_id,portion_state_hash,
 action,groups:[{group_id,amount}],reason}
```

action ist nur takeover_and_document oder document_current. document_legacy
gehört an die unveränderte C1-Route. Bestätigungsbody zusätzlich exakt
`{request_id,preview_hash,confirmation:true}`. Originale Arrayreihenfolge bleibt
Teil der Anfragequittung. Antwortlinien werden nach group_id sortiert.

`CapacityChange` exakt:

```text
{group_id,previous_segment_id,segment_id,
 carry:Money,returned:Money,basis:Money,not_before_date}
```

previous_segment_id ist bei Erstübernahme null. segment_id ist deterministisch
aus dem kanonischen neuen Abschnittsbeweis abgeleitet, einschließlich seiner
Basis, des Vorgängers, der Überträge, flachen R1-Referenzen und Datumsgrenze.
Öffentlich stehen nur Aggregate, keine R1-Quellen-IDs. changes enthalten bei
Erstübernahme alle Gruppen, später nur tatsächlich neu angelegte Nachfolger,
sortiert nach group_id. Ohne Freigabe ist die Liste leer.

`Line` exakt:

```text
{group_id,segment_id,amount,net,tax,
 gross_before,gross_after,net_before,net_after,tax_before,tax_after,
 remaining_gross,remaining_net,remaining_tax}
```

before/after sind der Verbrauch im konkreten Abschnitt. Historische Linien
binden seine ursprüngliche Basis; sie werden nicht gegen einen späteren
Nachfolger umgerechnet.

`Preview` exakt:

```text
{event_id,source_hash,expected_revision,state_hash,action,
 portion:Portion,amount,net,tax,lines,capacity_changes,reason,preview_hash,
 scope,tax_status,tax_result_available}
```

preview_hash ist SHA-256 über die ganze kanonische Vorschau ohne preview_hash.
`Entry` ist Preview ohne expected_revision,state_hash, dafür
`{id,sequence,revision,previous_state_hash,created_by,created_at}`.
sequence ist die eigene positive globale C2-Sequenz; revision die eigene
Eventrevision. Der C2-Lot wird dauerhaft durch `(entry_id,group_id)` innerhalb
dieser ausdrücklich eigenen Modulversion identifiziert.

## Persistenz und historische Prüfung

Genau sechs neue Tabellen, Präfix `business_accounting_capacity_`:

1. `handoffs`: document_id als PK/FK zur Rechnung, entry_id als eindeutiger FK
   zum ersten C2-Entry, handoff_json/handoff_sha256. Das kanonische vollständig
   geprüfte JSON bindet genaues Archiv, eingefrorenen C1-Gruppenstand und
   C1-Sequenzgrenze sowie Akteur/Zeit über den tragenden Entry. Einmalig je
   Rechnung, keine Rückgabe an C1. Keine zusätzliche SQL-Spalte id.
2. `segments`: 64-hexige id, document_id/group_id, positive Gruppenrevision,
   previous_id nullable mit UNIQUE, entry_id als FK zum tragenden Entry,
   segment_json/segment_sha256. Die genaue N/T/G-Basis, not_before_date und der
   vollständige Abschnittsbeweis stehen im kanonischen JSON.
   UNIQUE(document_id,group_id,revision). Vorstandsbeweis rekonstruiert
   tatsächliche frühere Linien, nicht nur selbst behauptete Überträge.
3. `releases`: eindeutige R1-Linienidentität
   `(refund_entry_id,origin_entry_id,group_id)` als PK und zusammengesetzter FK
   auf R1-Linien, segment_id als FK, reference_json/reference_sha256. Das
   vollständig geprüfte kanonische Referenz-JSON bindet feste N/T/G-Cents und
   den Originalzeilenhash.
   Jede Rücknahmelinie höchstens einmal über alle Abschnitte.
4. `entries`: id, eigene globale sequence UNIQUE, event_id FK, revision,
   document_id FK, portion_id UNIQUE, source_hash, previous_state_hash,
   entry_json/entry_sha256, proof_json, access_segments_json TEXT NOT NULL,
   created_by/created_at;
   UNIQUE(event_id,revision).
5. `lines`: entry_id FK, group_id, segment_id FK, sämtliche Line-Centfelder;
   PK(entry_id,group_id). Gruppe, Abschnitt und Rechnungsbindung zusätzlich
   domänenseitig vollständig geprüft.
6. `requests`: PK(user_id,request_id), event_id, unveränderte request_json/hash,
   entry_id UNIQUE FK. Requesthash bindet eigene Operation, Event und vollständige
   ursprüngliche Nutzlast einschließlich Arrayreihenfolge.

Ein Entry wird vor seinen abhängigen Handoff-/Segment-/Release-/Linienzeilen
eingefügt; alle Beweise werden vorher vollständig berechnet. Keine zyklische
FK-Pflicht von entries zurück auf handoffs. Derselbe Gesamtfehler rollt alles
einschließlich Quittung/Audit zurück. Alle sechs Tabellen unveränderlich;
SQLite zusätzlich REPLACE-Konfliktschutz, PG Runtime nur SELECT/INSERT.

access_segments_json ist eine kanonische, sortierte, eindeutige JSON-Liste
64-kleinhexiger Abschnitts-IDs. Sie enthält exakt die Vereinigung aller
`proof.prior_segments[*].segment_id` und `proof.new_segments[*].id`, auch für
Gruppen ohne positive Linie des Entries. Vor dem Lesen/Ausgeben gespeicherter
Fachdetails wird diese reine ID-Bindung gelesen und werden sämtliche über sie
und ihre Vorgänger gebundenen R1-Refundevents mit ihren vollständigen
C1-Origin-Quellumfängen frisch autorisiert. Die Integritätsprüfung vergleicht
die Liste exakt mit dem Proof und rekonstruiert diesen gegen die tatsächliche
Historie. Eine nachträglich verkürzte Liste besteht diese Prüfung nicht.
Spätere neue aktive Abschnitte erweitern keine alte Zugriffsliste rückwirkend.

Globale Portionseinmaligkeit gilt für die Vereinigung C1+C2. C2 prüft C1 und
seine eigenen Claims unter dem gemeinsamen Lock. C1 prüft neue Übernahme vor
neuem Schreiben; sein erfolgreicher Replay liegt davor. Der neue Validator
prüft die vereinigte Einmaligkeit und weist neue C1-Kundenlinien nach Übernahme
zurück. Zulässige spätere C1-Lieferanten-/andere Rechnungszeilen beeinflussen
den übernommenen Rechnungsstand nicht.

Die neue historische Prüfung rekonstruiert Abschnittsfolgen, genaue Überträge,
Linienstände, eindeutige R1-Claims, unveränderte Quellen, C1/R1-Beweise und
Requestbeziehungen. Alle Referenzen sind flach; keine rekursiv eingebetteten
ganzen Vorgängereinträge. Vollständige Quellenprüfung bleibt erforderlich,
auch wenn gespeicherte JSON-Hashes rechnerisch konsistent sind.

Der damalige Refundgate-Snapshot bindet seine beobachteten unveränderlichen
Finance-Zeilen/Import-/R1-Referenzen. Später hinzugekommene Finance-Refunds werden
nicht rückwirkend gegen die damalige Abwesenheitsentscheidung gehalten.
Historische Integrität prüft die tatsächlich gebundenen Quellen/Claims und die
konservativen Centgrenzen; sie behauptet keine aus Zeitstempeln rekonstruierbare
vollständige zeitliche Abwesenheit aller späteren Refunds.

## Replay, Clients und Fehler

Bestätigungsablauf: aktuelle vollständige Rechte/Betriebsgates; historische
Integrität; Lookup eigener originaler Requestquittung; bei exaktem Treffer
unveränderter alter Entry. Erst bei fehlendem Receipt aktuelle Kandidaten,
Übernahme, Reste, Gate, Datum und Vorschau prüfen. Geänderter Body unter alter
Request-ID ist 409. Andere ID/Nutzer umgehen keine ganze Portion.

Für die beiden Komponenten-Confirmrouten ist folgende zusätzliche
Fehlerinformation eng begrenzt zulässig:

```text
HTTP 409
{error:<verständlicher Konflikttext>,request_resolution:'not_accepted'}
```

Der Server setzt `request_resolution:'not_accepted'` ausschließlich, nachdem
unter derselben serialisierten Transaktion aktuelle vollständige Rechte,
Betriebsgates und historische Integrität geprüft wurden und der Lookup
**keine Quittung für diese Benutzer-/Request-ID im jeweiligen C1- oder
C2-Protokoll** gefunden hat. Erst danach
auftretende 409-Konflikte der aktuellen Vorbereitung oder Vorschau werden
so gekennzeichnet, vor jeder neuen Insert-/Auditwirkung. Diese Kennzeichnung
bestätigt, dass der unveränderte übermittelte Befehl nicht angenommen wurde.

Vor dem Receiptlookup ausgelöste Modus-, Restore-, Runtime-, Rechte- oder
Integritätsfehler tragen diese Kennzeichnung nicht. Auch ein Konflikt mit
einer bereits vorhandenen anderslautenden Requestquittung bleibt unmarkiert.
Die Sicherheitsgates bleiben vor dem Lookup; die Zusatzinformation verschiebt
oder umgeht sie nicht. Nur HTTP 409 mit exakt diesem Feldwert wird als solche
Auflösung anerkannt. Keine Textauswertung der deutschen Fehlermeldung.

Die neue C1-Schreibsperre liegt nach dessen bisherigem erfolgreichen
Receipt-Replayzweig in der öffentlichen confirm-Methode; preview prüft sie vor
neuer Vorbereitung. Altes Feature und writes_allowed bleiben für die üblichen
Rechte/Betriebsgates erhalten. Alte Clients können historische Quittungen
wiederholen; nach dem fehlenden Receiptlookup abgewiesene alte Vorschauen nach
Übernahme erhalten den gekennzeichneten 409 mit verständlich formulierter
Aufforderung zur erneuten Prüfung. Alte erfolgreiche Antworten, Requestbodies,
Proofs und Horizonte werden dadurch nicht verändert.

Beide Clients verwenden einen logischen Event-Pendingschlüssel über C1/C2,
speichern aber den ursprünglichen Pfad, vollständigen Body und Request-ID
unverändert. Keine automatische Umschreibung auf den neuen Pfad. C2-Pending
wird vor Retry immer neutral gezeigt, ohne gespeicherte Kapazitäts-/Ursprungs-
details. Preflight liest den gespeicherten Writer-State frisch; Retry selbst
prüft serverseitig alle historischen/neuen Quellrechte. Keine aktuelle
Kandidatenpflicht im Client für historischen Replay und keine zusätzliche
Autorisierungsroute. Details erst aus der autorisierten erfolgreichen Antwort.

Flutter ermöglicht eng begrenzt identische bestehende Pendingoperationen nach
Capability-Generationswechsel unter derselben Identität/aktuellen Rechten.
Änderung während des Requests erhält den unklaren Pendingzustand; kein lokal
erzeugter 409 darf ihn löschen. Ausschließlich für C1-/C2-Komponenten-Confirms
bleiben alle unmarkierten 409 sowie 403/404/423, 5xx und Netzfehler pending.
Ein nach positivem Preflight auftretender Rechteentzug oder eine Restore-/
Modussperre beweist keinen unangenommenen ursprünglichen Auftrag. Erst eine
erfolgreiche Antwort oder ein serverseitiger 409 mit exakt
`request_resolution:'not_accepted'` löst diesen unklaren Bestätigungsvorgang
auf und erlaubt eine neue getrennte Vorschau/Bestätigung. Ein alter Server,
der nur unmarkierte 409 liefert, kann damit keinen unklaren Komponentenauftrag
stillschweigend auflösen. 401 und Sitzungswechsel behalten den bestehenden
Identitätsschutz; kein Retry unter anderem Benutzer. Die Behandlung anderer
Operationen und anderer bestehender Eingabefehler wird dadurch nicht geändert.

Fehler: 400 bei ungültigen Eingaben, unbekannten Feldern oder nicht exakter
Portionssumme; 403/404 bei fehlenden aktuellen Rechten/Quellen ohne Fremddetails;
409 bei Quell-/Proof-/Versions-/Zustands-/Rest-/Datums-/Gatekonflikt; 423 bei
deaktiviertem Finanzmodul; 405 bei falscher Methode. Gespeicherte ungültige
Zahlen/Strukturen werden wie C1/R1 zu 409 normalisiert.

blocked_reason zusätzlich zu den bisherigen C1-Quellenfällen:
not_customer_receipt, refund_origin_unresolved, source_access_required,
receipt_before_capacity, legacy_writer_required, group_capacity_exceeded,
unallocated, fully_documented; null bei möglicher konkreter Aktion.

## Horizonte, Projektionen und Nachweisgrenze

C1/R1-Proofschema, DDL/Guards, Horizonte und alte Antworten bleiben unverändert,
einschließlich R1 capacity_released:false. Der neue spätere Freigabenachweis
gehört allein zum neuen Modul. Keine Änderung an Zahlungen, originalen
Allocations, OP, Mahnung, Bank-/Financeprojektionen oder CashEvent-Quellen.

Eigener Teilhorizont K1, exakt:

```text
{schema_version:1,
 table_counts:{business_accounting_capacity_handoffs:<count>,
               business_accounting_capacity_segments:<count>,
               business_accounting_capacity_releases:<count>,
               business_accounting_capacity_entries:<count>,
               business_accounting_capacity_lines:<count>,
               business_accounting_capacity_requests:<count>},
 sha256}
```

K1 bindet nach vollständiger Integritätsprüfung alle eigenen vollständigen
Zeilen einschließlich Requests, deterministisch sortiert. Vollständig fehlendes
Modul ohne Tabellen/Marker ergibt null; Teilinstallation oder beschädigte
Historie einen Fehler. Hook/Inspect führen kein DDL, keine Migration und keinen
Commit aus. Der gemeinsame H5-Horizont lautet exakt:

```text
{schema_version:5,prejournal:<H1>,allocations:<A1>,components:<C1>,
 refunds:<R1>,capacity:<K1>}
```

Neue Betreiberfreigaben benötigen Berichtschema 6 auch bei leerem K1-Modul.
Die bisherigen übrigen Berichts-/externen Abgleichsfelder bleiben unverändert.
Historisches H4 und seine Schema-5-Parser behalten die festen bisherigen vier
Teilbereiche; sie erhalten kein nachträgliches capacity-Feld. Frühere bereits
erfolgreiche identische Betreiberquittungen sind nur unter den bisherigen
Betreiber-/Stillstands-/Restore-ID-Grenzen bei bereits aufgehobener Sperre
wirkungslos replaybar. Sie entsperren keinen neuen Restore; eine neue Freigabe
braucht vollständiges aktuelles H5. Migration/Inspect verändern keine Altdaten.
Diese Festlegung ist Implementierungsvertrag, noch kein Ausführungsnachweis.

Gezielte Abnahme umfasst exakte 6,34-Cent-Wiederbelegung und Restüberträge,
Mehrgruppenatomarität, doppelte Release-/Portionsansprüche, konkurrierende
C1/C2/Finance/R1-Schreiber, alte Pendingquittungen, fehlende Rechte,
nicht importierte Refunds, spätere Refunds, Datumssperren, manipulierte
Vorstände trotz konsistenter Hashes, SQLite-/PG-Guards, Restore und beide Clients.
Ergebnisse werden erst nach tatsächlicher Ausführung eingetragen.
