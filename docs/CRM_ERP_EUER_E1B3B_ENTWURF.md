# E1b-3b: genaue Restkapazitäten nach Erstattungen – Entwurf

Stand: 03.11.2026. **Entwurf, nicht implementiert und nicht getestet.**
Lesende Vorbereitung anhand von E1b-2 (`2261712`) und dem noch nicht separat
committeten E1b-3a-Arbeitsstand. Dieser Text ist kein Implementierungsvertrag
und kein Fertignachweis. Vor Entwicklung legt der Hauptagent den endgültigen
Vertrag fest; E1b-3a erhält zuvor seinen eigenen Abschlusscommit.

Grundlagen: [E1b-2](CRM_ERP_EUER_E1B2_API.md),
[E1b-3a](CRM_ERP_EUER_E1B3A_API.md),
[Gesamtentwurf E1b](CRM_ERP_EUER_E1B_ENTWURF.md).

## Empfohlener kleinster zusammenhängender Schritt

Ein neues additives Modul übernimmt die freien dokumentarischen Cents einer
**ganzen normalen Ausgangsrechnung mit allen ihren Gruppen** und führt neue
positive Komponenten in unveränderlichen Restabschnitten. Die erste Übernahme
und die erste neue ganze Einnahmenportion werden gemeinsam vorgeschlagen und
bestätigt. Es gibt keinen schreibenden GET und keine automatische Freigabe beim
Bestätigen eines R1-Erstattungsursprungs.

Die Übernahme erfolgt je Rechnung, nicht pauschal für das Unternehmen und nicht
einzeln je Gruppe. Bis zur Übernahme bleibt C1 für diese Rechnung der einzige
positive Schreiber. Danach ist ausschließlich der neue Schreiber zuständig;
C1 bleibt für erfolgreiche identische Wiederholungen erhalten. Eine Portion
gehört bereits genau einer Rechnung. Deshalb kann eine gemischte Verteilung
über mehrere Gruppen atomar wechseln, ohne eine Portion auf zwei Schreiber
aufzuteilen. Andere Portionen desselben CashEvents dürfen zu anderen Rechnungen
und damit zunächst noch zu C1 gehören.

Eine globale sofortige C1-Schreibsperre ist für diesen begrenzten Schritt nicht
empfehlenswert: Ein alter, noch undokumentierter Einnahmenanteil würde danach
ein neues Lot erzeugen, das R1 nicht referenzieren kann. Ein noch ungeklärter
alter Refund könnte dadurch seinen dokumentierbaren Ursprung verlieren.

## Reichweite von Lots und Rücknahmen

| Gegenstand | Verhalten dieses Schritts |
| --- | --- |
| Bestehender C1-Lot | Unverändert; weitere Rücknahme durch R1 bleibt möglich. |
| Noch freie Rechnung ohne Übernahme | Neue ganze Einnahmenportionen weiter durch C1 dokumentierbar. |
| Übernommene Rechnung | Neue ganze Einnahmenportionen ausschließlich im neuen Modul. |
| Neue positive Linie | Eigener versionierter Lot mit festen tatsächlichen N/T/G-Cents und Restabschnittsbindung. |
| R1-Rücknahmelinie gegen C1 | Ihre festen N/T/G-Cents können genau einmal in einen neuen Abschnitt übernommen werden. |
| Refund, der einen neuen Lot benötigt | Weiter ungeklärt; R1 wird nicht umgedeutet und sein zusammengesetzter C1-FK bleibt unverändert. |
| Refundportion, die C1- und neue Lots benötigt | Nicht teilweise bestätigen; die ganze Portion bleibt bis zur späteren Refundversion offen. |

Dieser Schritt ermöglicht die Wiederbelegung nach bestätigten R1-Rücknahmen.
Er behauptet keine vollständigen wiederholten Erstattungs-/Wiederzahlungszyklen
für neue Lots. Dafür folgt eine additive Refundversion mit versionierten
Ursprungsreferenzen. Bei deren Einführung darf R1 nicht parallel dieselben
Lotreste verbrauchen: erfolgreicher R1-Replay bleibt, neue Bindungen wechseln
atomar. Ein neuer Refundschreiber muss bereits von R1 zurückgenommene Cents in
den ursprünglichen kumulativen Lotstand einbeziehen; diesen Zähler nicht auf
null setzen. Die alte Lotbasis bleibt auch dann unverändert.

## Exakte Abschnittsrechnung

Die archivierte `group_id` bleibt die fachliche Gruppenidentität. Ein Abschnitt
erhält zusätzlich eine eigene unveränderliche Identität und einen eindeutigen
Vorgänger. Seine N/T/G-Basis ist **nicht** die ursprüngliche Rechnungsbasis.

Für die erste Übernahme gilt je Gruppe, getrennt in ganzen Netto-, Steuer- und
Bruttocents:

```text
carry_N = archived_N - sum(C1_line.net)
carry_T = archived_T - sum(C1_line.tax)
carry_G = archived_G - sum(C1_line.amount)

segment_N = carry_N + sum(newly_claimed_R1_line.net)
segment_T = carry_T + sum(newly_claimed_R1_line.tax)
segment_G = carry_G + sum(newly_claimed_R1_line.amount)
segment_G = segment_N + segment_T
```

Die C1-Linien werden mit ihren bestehenden Quellen-, Archiv- und kumulativen
Beweisen validiert. Die R1-Linien werden mit vollständiger R1-Ledgerprüfung
validiert. Weder ein gespeicherter Hash allein noch saldiertes Rechnungsbrutto
ersetzt diese Prüfung. Es gelten nichtnegative Werte. Eine Nullkapazität bleibt
als Gruppenübernahme belegbar, wird aber nicht zur Eingabe angeboten.

Innerhalb eines Abschnitts gilt bei kumuliertem Verbrauch C:

```text
Tax(C) = floor((2*C*segment_T + segment_G) / (2*segment_G))
Net(C) = C - Tax(C)
new_line_tax = Tax(C + amount) - Tax(C)
new_line_net = amount - new_line_tax
0 < amount <= segment_G - C
```

Bei später hinzugekommenen R1-Rücknahmen wird der bisherige Abschnitt durch
einen neuen unveränderlichen Nachfolger abgelöst. Der Übertrag ist exakt
`alte Abschnittsbasis minus tatsächliche bisherige Abschnittslinien`, getrennt
für N/T/G. Hinzu kommen ausschließlich noch nie übernommene Rücknahmelinien.
Der Nachfolger beginnt bei C=0. Ohne neue Rücknahmen bleibt derselbe Abschnitt
aktiv; keine willkürlichen Resets bei jeder Einnahme.

Ein Abschnitt wird erst gemeinsam mit einer neuen bestätigten Einnahmenportion
gespeichert. Vorschau/GET berechnen gegebenenfalls einen möglichen Nachfolger
ohne Persistenz. Mehrere inzwischen bestätigte R1-Linien derselben Gruppe
können gemeinsam in diesen Nachfolger eingehen. Ein eindeutiger Vorgänger
verhindert konkurrierende Nachfolger. Eine übernommene R1-Linie wird niemals
nochmals gutgeschrieben.

Beispiel: Die voll belegte Gruppe 119,00 = 100,00 + 19,00 enthält den mittleren
Lot 39,67 = 33,33 + 6,34. Dessen vollständige R1-Rücknahme ergibt bei leerem
sonstigem Rest einen neuen Abschnitt mit genau 33,33/6,34/39,67. Vollständige
Wiederbelegung muss wieder 33,33/6,34 liefern. Neuaufteilung anhand 19/119 wäre
hier falsch. Bei einem nicht leeren Altabschnitt werden dessen genaue übrige
Cents addiert, nicht erneut aus dem ursprünglichen Steuersatz berechnet.

## Gate für ungeklärte und noch nicht importierte Finance-Refunds

Vor der ersten Rechnungsübernahme und vor **jeder weiteren Übernahme von
Rücknahmecents** prüft der Server unter derselben Schreibserialisierung alle
ursprünglichen `business_payment_allocations` dieser Rechnung, deren Payment
`kind='refund'` hat. Ausgangspunkt ist Finance, nicht die kleinere E1a- oder
R1-Menge. Die Prüfung ist global und wird nicht nach Betrachter gefiltert.

Jede solche ganze Allocation benötigt einen gültigen übernommenen E1a-Refund
und eine gültige ganze R1-Ursprungsbindung. Fehlt eine dieser Bindungen,
verhindert `refund_origin_unresolved` die Rechnungsübernahme beziehungsweise
die zusätzliche Kapazitätsfreigabe. Ein bereits vorhandener, aber noch nicht
übernommener Finance-Refund darf nicht versehentlich unsichtbar werden.

Vor der ersten Übernahme darf C1 weiterhin belegbare ursprüngliche Einnahmen
innerhalb seiner unveränderten Restgrenzen dokumentieren. So können fehlende
C1-Ursprünge für R1 hergestellt werden; erst anschließend wird übernommen.
Nach erfolgter Übernahme wird niemals auf C1 zurückgeschaltet.

Später ungeklärt hinzugekommene Refunds entziehen bereits korrekt übernommene
Cents nicht rückwirkend. Der bestehende aktive Abschnitt darf innerhalb seines
schon bestätigten Rests weiter verwendet werden; **weitere** R1-Cents bleiben
bis zur Klärung außerhalb dieses Abschnitts. Das UI unterscheidet daher
`current_capacity` von `pending_return_capacity` und zeigt keine Freigabe der
letzteren an. Ein Betrag, der nur mit diesen noch nicht freigegebenen Cents
passt, bleibt gesperrt. Dies verhindert gleichzeitig einen historischen Reset
und die Behauptung, ein ungeklärter Refund sei erledigt.

Unzugeordnete Refundreste werden keiner Rechnung geraten zugeordnet. Sie
bleiben separat ungeklärt und erzeugen keine Kapazität. Die lokale Gateaussage
gilt ausschließlich für vorhandene ausdrückliche Rechnungszuordnungen und ist
kein vollständiger Unternehmensabgleich. Eine gemischte/NULL-Kundenquelle,
deren relevante ganze Refundportion R1 nicht binden kann, blockiert die
zugehörige Freigabe ebenfalls.

Die aktuelle Vorschau bindet einen opaken Fingerabdruck des vollständig
gelesenen relevanten Finance-/Import-/R1-Stands. Ein konkurrierender neuer
Refund, Import oder Ursprung ändert diese Vorschau. Historische Antworten
behalten den damals beobachteten Stand; später angelegte Refunds machen keine
alte zulässige Entscheidung rückwirkend ungültig. Zeitstempel ersetzen keine
Sequenz- oder Quellenbindung. Der endgültige Vertrag muss unterscheiden
zwischen diesem aktuellen Gate und dem historischen Nachweis der tatsächlich
übernommenen Linien; er darf aus einem alten Snapshot keine zeitlich unbegrenzte
Abwesenheit unbekannter Refunds ableiten.

Öffentlich erscheinen keine fremden Refund-/Payment-/Actor-IDs oder versteckte
Anzahlen. Eine fehlende vollständige Berechtigung wird durch einen neutralen
Sperrhinweis dargestellt. Globale Centgrenzen bleiben unabhängig von Rechten.

## API, Writerentscheidung und Wiederholungen

Vorschlag: zusätzliche Fachroute
`/api/v1/business/accounting/components/v2/events/{event_id}` mit State,
Portions, History, Preview und Confirm. Die Transportbasis `/api/v1` bleibt;
beide Clients unterstützen derzeit diese Basis. Neues Feature additiv neben
`accounting_document_components`, kein ersetzender Transportversionswechsel.

Der neue State/Portions-Vertrag bezeichnet je ganzer Portion ihren aktuellen
Schreiber, ihren Dokumentübernahmestand und die angebotene Aktion. Zulässige
Aktionen sind sinngemäß `document_legacy`, `takeover_and_document` und
`document_current`. Technische Versionsnamen gehören nicht in Produkttexte.
Neue Clients wählen den Pfad je Portion; ein Event kann beide Schreiber haben.
Bestehende C1-Historie wird mit ihrer ursprünglichen Antwort/versionierten
Hülle lesbar, nicht in eine neue vermeintliche C1-Antwort umgeschrieben.

Die erste neue Bestätigung bindet alle Gruppen der Rechnung, den vollständigen
C1-Gruppenstand, die übernommenen R1-Linien und den Gatefingerabdruck. Bei
mehreren Gruppen gibt der Benutzer weiterhin ausdrücklich positive Bruttocents
ein; Summe exakt ganze Portion. Keine automatische Verteilung oder Kürzung.
Die Besitzübernahme aller Gruppen und sämtliche neuen Linien sind atomar.

C1 `preview` prüft vor neuer Vorbereitung, ob die konkrete Rechnung bereits
übernommen wurde. C1 `confirm` behält zunächst aktuelle Rechte/Betriebsgates,
historische Integrität und den bisherigen exakten Receiptlookup bei. Erst nach
diesem erfolgreichen Replayzweig folgt die neue Übernahmesperre. Ein bereits
angenommener alter Befehl liefert deshalb exakt seine alte Antwort; ein nicht
angenommener alter Befehl für eine inzwischen übernommene Rechnung erhält einen
terminalen 409 mit Hinweis auf erneute Prüfung. Die Sperre gilt in der
öffentlichen Domänenmethode, nicht nur im HTTP-Dispatcher.

Der neue Schreiber prüft unter demselben Lock, dass die `portion_id` weder in
C1 noch im neuen Modul verbraucht ist. C1 prüft vor neuem Schreiben zusätzlich
die Rechnungsübernahme. Neue Einträge haben `UNIQUE(portion_id)`; der neue
Integritätsvalidator prüft die vereinigte Einmaligkeit beider Versionen.
Damit braucht der kleinste Schritt keine rückwirkend befüllte gemeinsame
Claimtabelle: Unveränderliche C1-Claims plus einseitige, dauerhafte Übernahme
und gemeinsame Serialisierung schließen Doppelverbrauch aus. Falls eine
explizite Claimtabelle gewählt wird, muss sie alte Claims vollständig binden
und auch sämtliche noch erlaubten neuen C1-Einträge atomar aufnehmen.

Kein Client ersetzt Pfad, Inhalt oder Request-ID eines offenen Befehls.
Pending v1 wird zuerst unverändert am gespeicherten v1-Pfad wiederholt. Erst
nach serverseitigem terminalem 409 kann eine neue Vorschau am aktuellen Pfad
entstehen und neu bestätigt werden. Netzfehler/5xx/423 bleiben offen.

Zwingende Clientanpassungen: ein gemeinsamer logischer Event-Pendingschlüssel
über beide Pfade; gespeicherten Pfad separat erhalten. Web prüft Pending
aktuell auf exakte Pfadgleichheit, Flutter blendet beim Pfadwechsel sonst den
alten Body aus, während `pending(key)` weiterhin blockiert. Flutter braucht
außerdem eine eng begrenzte Wiederholungsmöglichkeit für unveränderte alte
Operationen nach Capability-Generationwechsel; derzeit wird vor HTTP abgewiesen.
Identität und aktuelle Rechte bleiben erforderlich. Generationwechsel während
des Retries darf keinen lokalen terminalen 409 erzeugen, der einen womöglich
angenommenen Befehl löscht. Historische Pending-Details bleiben bis zu frischer
vollständiger Autorisierung verborgen.

## Persistenz, Integrität und Projektionen

Empfohlen sind eigene unveränderliche Tabellen für Rechnungsübernahmen,
Abschnitte, übernommene R1-Linien sowie neue Einträge/Linien/Requests. Einmalig:
Rechnung/Archivbindung, Abschnittsvorgänger, R1-Linienidentität
`(refund_entry_id,origin_entry_id,group_id)` und ganze neue `portion_id`.
Übernahme und Abschnitte werden von einer tatsächlichen neuen Bestätigung
getragen; keine verwaisten Reservierungen aus Vorschauen.

Beweise referenzieren geprüfte Quellen und frühere Zeilen flach mit Hashes.
Der Validator rekonstruiert die tatsächlichen Vorstände aus früheren Linien;
ein lediglich intern konsistent behaupteter Übertrag genügt nicht. Neue
kundenseitige C1-Zeilen nach Rechnungsübernahme sind ein Integritätsfehler.
Spätere C1-Lieferantenzeilen oder C1-Zeilen anderer Rechnungen sind weiterhin
zulässig und verändern keine alten Übernahmebeweise.

Alle Grenzen, Zustandsprüfung, neue Abschnitte, Übernahmereferenzen, positive
Linien, Quittung und Audit liegen in derselben SQLite-IMMEDIATE-/PG-Advisory-
Transaktion. Kein Akteurfilter und keine separate Writer-Sperre pro Gruppe.
Teilfehler rollen den ganzen Mehrgruppenbefehl einschließlich Übernahme zurück.

C1 `_pool`, seine Formeln, alten Linien, Proofschemas, DDL und Guards bleiben
unverändert. R1 bleibt ebenfalls unverändert einschließlich
`capacity_released:false`: eine eigene spätere Übernahmeaussage wird nicht
rückwirkend in die R1-Antwort hineingeschrieben. H1/A1/C1/R1 behalten ihre festen
Teilbereiche; das neue Modul erhält einen eigenen zusätzlichen Teilhorizont
und eine neue Operator-Berichtsversion. Alte Quittungen entsperren keinen
neuen Restore.

Finance, originale Allocations, OP, Mahnung, Bank-/Paymentprojektionen und
CashEvent-Quellen bleiben unverändert. Ein neuer konsolidierter Dokumentstand
zeigt getrennt die insgesamt dokumentierten positiven Cents, bestätigte
Rücknahmen, bereits übernommene Rücknahmen und verfügbare Abschnittscents.
Alte `documented_*`-C1-Felder werden nicht still in Nettobestände umgedeutet.
Weiterhin `tax_status:'unconfigured'`, `tax_result_available:false`; keine
fertige EÜR oder steuerliche Gegenbuchung.

## Noch im endgültigen Vertrag festzulegen

1. Exakte neue DTO-/Tabellen-/Fehlernamen und der additive Restorehorizont.
2. Zeitregel für Wiederbelegung: Der bisherige Vertrag verlangt nur für R1
   `origin.cash_date <= refund.cash_date`. Er legt keine zusätzliche
   Wiederbelegungs-Datumsregel fest. Soll `new_receipt.cash_date` mindestens
   das größte Datum der enthaltenen Refunds erreichen, muss dies ausdrücklich
   geregelt werden; eine gemischte Abschnittsbasis darf keine nur teilweise
   zulässigen zeitlichen Cents verdecken. Keine stillschweigende Steuerperiode.
3. Ob eine erste Übernahme ohne tatsächlich neue R1-Cents überhaupt angeboten
   wird. Empfehlung für diesen kleinen Schritt: nein; C1 bleibt bis zum
   konkreten Wiederverwendungsbedarf zuständig.

## Gezielte spätere Nachweise

Noch keine dieser Prüfungen wurde für diesen Entwurf ausgeführt:

- Voller mittlerer 6,34-Steuercent-Lot, Teilrücknahme, nicht leerer Altabschnitt
  und zwei aufeinanderfolgende Abschnittswechsel ohne Centverlust.
- Eine ganze Mehrgruppenportion übernimmt alle Gruppen oder keine;
  Fehler nach erster Linie/Übernahme/Audit rollt alles zurück.
- Zwei PG-Verbindungen konkurrieren C1 gegen Übernahme, C2 gegen C2 sowie
  Übernahme gegen neuen Finance-Refund/R1. Genau ein passender Stand gewinnt.
- Alte angenommene Pendingquittung bleibt exakt, alte unangenommene Vorschau
  scheitert nach Übernahme ohne Wirkung; neue Request-ID umgeht keine Portion.
- Noch nicht importierter Finance-Refund und importierter ungebundener Refund
  verhindern neue Freigabe. Fehlenden C1-Ursprung vor Übernahme noch herstellen.
- Neuer ungeklärter Refund nach Übernahme verändert keine Historie, gibt keine
  neuen Cents frei und erzeugt keinen Rückfall zum alten Schreiber.
- Vorgetäuschter carry-/before-Stand, doppelte R1-Übernahme, verwaister Abschnitt
  und neue C1-Zeile nach Übernahme werden auch bei neu berechneten JSON-Hashes
  abgewiesen; frühere Horizonte und Proofs bleiben gültig.
- Web/Flutter: gemischtes Event mit zwei Rechnungs-Schreibern, neutrale alte
  Pendingwiederholung, Generation-/Rechtewechsel und keine Offenlegung fremder
  Refunddetails; vorhandene Finance-/OP-Projektionen unverändert.
