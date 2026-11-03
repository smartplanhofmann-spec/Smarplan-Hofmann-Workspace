# E1b-3c: Erstattungen auf wiederverwendete Beleganteile – Entwurf

Stand: 03.11.2026. **Reine Planung, nicht implementiert und nicht getestet.**
Dieser neue Entwurf gehört ausdrücklich nicht in den Abschlusscommit oder
Prüfnachweis von E1b-3b. Er wurde während dessen finaler Prüfungen aus dem
aktuellen Arbeitsstand vorbereitet; ein endgültiger 3c-Vertrag muss später
den tatsächlich abgeschlossenen 3b-Commit als Basis binden.

Gelesene Grundlagen: [R1-Erstattungsursprünge](CRM_ERP_EUER_E1B3A_API.md),
[C2-Restkapazitäten](CRM_ERP_EUER_E1B3B_API.md), deren Module und bestehende
C1-Quellen. Keine Änderung an Code, aktuellen Betriebs-/API-Dokumenten,
Migrationen oder Tests durch diesen Entwurf.

## Kleinster vollständiger nächster Zyklus

Eine neue Refundversion R2 kann eine ganze ursprüngliche Refund-Allocation
an C1-Lots, C2-Lots oder eine ausdrückliche Mischung beider binden. Ihre exakten
Rücknahmecents können anschließend über **denselben vorhandenen C2-Schreiber**
wieder in neue Restabschnitte eingehen. Erst diese Kombination schließt die
bisherige Lücke „neue Aufteilungen noch nicht als Erstattungsursprung verfügbar“.
Eine isolierte R2-Bindung ohne erneute Kapazitätsübernahme würde sie nur teilweise
schließen und ist deshalb nicht der empfohlene Abschlussumfang.

Für den kleinsten Schritt erfolgt ein R1→R2-Wechsel nur für Rechnungen, die
bereits vollständig in C2 übernommen wurden. Dadurch bleiben unübernommene
Rechnungen in ihren bestehenden C1/R1-Abläufen. Für die erste C2-Übernahme gilt
weiterhin der bisherige R1-Ablauf. Eine schon in C2 übernommene Rechnung kann
mit der ersten neuen ganzen R2-Ursprungsbindung atomar zu R2 wechseln; die
gewählten Ursprünge dürfen dabei schon gemischt oder ausschließlich C1 sein.

R2 erzeugt keine neue Geldbewegung, keine zweite OP-Wirkung und keine
Steuerbuchung. Unzugeordnete Refundreste bleiben ungeklärt. Normale EUR-
Rechnungs-, Kunden-, CashDate- und Quellenregeln bleiben bestehen. Die
steuerliche Einordnung bleibt unconfigured.

## Ein Refundschreiber je ganzer Rechnung

Ein neuer unveränderlicher R2-Übernahmedatensatz bindet die Rechnung, ihren
gültigen C2-Übernahmestand und sämtliche bis dahin vorhandenen R1-Ansprüche
dieser Rechnung. Er entsteht atomar mit dem ersten neuen R2-Entry.

Vorher darf R1 neue ganze Refundportionen dieser Rechnung binden; nachher nur
bereits erfolgreiche ursprüngliche Requests exakt wiederholen. Die zusätzliche
R1-Schreibsperre liegt nach aktuellem Zugriff/Betriebsgates, historischer
Integrität und erfolgreichem Receipt-Replay. Erst ein neuer Request wird vor
der Vorbereitung am permanenten Rechnungsbesitz geprüft. Keine Sperre allein
anhand eines umschaltbaren Clientfeatures.

Der Übergang verlangt ausdrücklich **nicht**, dass bereits alle Refunds
geklärt sind: Die gerade offene Portion und weitere offene Portionen sollen
erst durch R2 geklärt werden können. Eine solche Vollständigkeitssperre hier
wäre ein Zirkelschluss. Der positive C2-Schreiber behält dagegen sein globales
Finance-Refundgate für zusätzliche Freigaben.

R1- und R2-Claims einer ganzen Refundportion müssen gemeinsam eindeutig sein:
R2 prüft unter dem gemeinsamen Lock beide Bestände; der dauerhafte
Rechnungsübergang verhindert neue R1-Claims danach. Der Validator prüft die
Vereinigung von refund_allocation_id/portion_id und die eingefrorenen R1-
Rechnungsbeiträge. Ein neues R1-Dokument nach Übergang ist ein Integritätsfehler.
R1-Einträge anderer Rechnungen bleiben erlaubt.

Ein Refund-CashEvent kann mehrere ursprüngliche Rechnungsportionen enthalten.
Die Writerentscheidung erfolgt deshalb je Portion/Rechnung, nicht für das
ganze Event. Eine einzelne Portion wird niemals zwischen R1/R2 geteilt.
Eine Mischportion mit mehreren Lots wird vollständig bestätigt oder gar nicht.

## Feste Lotidentität und kumulative Cents ohne Versionsreset

Die neue Identität eines positiven Ursprungslots ist
`(origin_version:'c1'|'c2',entry_id,group_id)`. Die Version gehört zu
Eindeutigkeit, Hashes, Auswahl, Zeilen und flachen Referenzen. Eine zufällig
gleiche Entry-ID in zwei Modulen ist keine gleiche Quelle.

Für jeden Lot gilt unverändert seine tatsächliche eingefrorene positive
N/T/G-Linie, bei C2 also die konkrete Abschnittszuweisung. Weder die
Rechnungsbasis noch der heutige Abschnittsrest ersetzt diese Lotbasis.

```text
R_before(C1-Lot) = Summe gültiger alter R1-Rücknahmen
                  + Summe aller früheren R2-Rücknahmen dieses Lots
R_before(C2-Lot) = Summe aller früheren R2-Rücknahmen dieses Lots

Tax(R) = floor((2*R*lot_T + lot_G) / (2*lot_G))
Net(R) = R - Tax(R)
new_tax = Tax(R_before + amount) - Tax(R_before)
new_net = amount - new_tax
0 < amount <= lot_G - R_before
```

Die alten R1-Netto-/Steuersummen werden gegen dieselbe kumulative Lotregel
geprüft und bilden den Anfangsstand, ohne neue Gegenbuchung. R2 beginnt für
einen teilweise zurückgenommenen C1-Lot nicht bei R=0 und rechnet auch nicht
mit dessen verbleibendem Rest als neuer Lotbasis. Vollständige Rücknahme
erreicht über R1+R2 exakt die ursprünglichen Lotcents.

Eine R2-Refundportion darf mehrere Lots derselben Gruppe und beide Versionen
enthalten. Positive Eingabebeträge summieren sich exakt zur ganzen Allocation.
Jede Linie braucht dieselbe archivierte Rechnung/Kundenbindung, EUR und
`origin.cash_date <= refund.cash_date`. Die positive Wiederbelegung bleibt
anschließend an die bestehende konservative Abschnitts-Datumsgrenze gebunden.

## Keine Umdeutung des bestehenden Release-Fremdschlüssels

`business_accounting_capacity_releases` referenziert ausdrücklich R1-Linien.
Dieser FK und seine Guard-/DDL-Prüfsummen bleiben unverändert. R2-Linien werden
dort weder eingeschoben noch als R1-Linien ausgegeben, auch wenn ihr Ursprung
ein C1-Lot ist.

Eine neue additive R2-Releaseclaimtabelle referenziert echte R2-Linien und
bestehende C2-Abschnitte. Die vereinheitlichte interne Returnidentität enthält
mindestens `refund_version`, Refund-Entry, `origin_version`, Ursprungseintrag
und Gruppe. R1- und R2-Claims dürfen sich nicht durch identische Roh-IDs
überdecken. Jeder vollständige Rücknahmelinienbetrag wird genau einmal in
einen Abschnitt übernommen; keine zusätzliche Teilfreigabesemantik.

Der aktuelle C2-Pfad, sein positives Entry-/Preview-DTO und seine sechs
bestehenden Tabellen können erhalten bleiben. Neue Entries bekommen ein
ausdrücklich versioniertes internes Proofschema. Neue Abschnittsbeweise
verwenden versionierte Returnreferenzen. Alte Proofschema-1-Entries, ihre
Segment-IDs, Antworten, Quittungen und Zugangsliste bleiben unverändert.

Neue C2-Freigaben prüfen das Financegate gegen die Vereinigung gültiger R1-
und R2-Bindungen. Noch nicht importierte oder ungebundene Refund-Allocations
bleiben global sperrend für neue Freigaben; schon gültige aktuelle Kapazität
bleibt im bisherigen Rahmen nutzbar. Neue R2-Rücknahmecents werden in derselben
Vorschau als pending/offered gezeigt und erst mit der nächsten echten
C2-Bestätigung übernommen. Es entsteht keine zweite positive API-Schreibroute.

## Gemeinsame chronologische Prüfung statt gegenseitiger Vollrekursion

Die neue Abhängigkeit lautet C2-Lot → R2-Rücknahme → späterer C2-Abschnitt.
Ein naives `R2._ledger()` ruft C2-Historie auf, während `C2._sources()` R2-Historie
aufruft, und würde zyklisch werden. Empfehlenswert ist ein gemeinsamer rein
lesender Validator mit getrennten, bereits geprüften Zuständen für positive
Lots, Rücknahmeansprüche und aktive Abschnitte.

Alte C2-Proofschema-1-Entries werden für den Merge ausschließlich als
Beobachter eines virtuellen R2-Kopfs 0 behandelt. Ihre gespeicherten Proofs
werden dafür nicht verändert. Ihre fachliche Prüfung bleibt streng bei ihren
alten R1-Quellen und ihrem bisherigen Proofschema. Schema 1 bildet einen
zusammenhängenden Präfix; nach einem Schema-2-Entry ist Schema 1 unzulässig.
Eine zusätzliche Startgrenztabelle ist mit dieser Mergeregel nicht erforderlich.

Die neuen Vorgänge speichern unter demselben globalen Schreiblock:

- jeder neue R2-Proof den exakt zuvor vorhandenen globalen C2-Sequenzkopf;
- jeder neue C2-Proof den exakt zuvor vorhandenen globalen R2-Sequenzkopf.

Ein beobachteter Gegenkopf k sagt beides: Der Vorgang liegt nach Gegeneintrag k
und vor Gegeneintrag k+1, sofern dieser existiert. Bloßes topologisches Sortieren
der Verweise auf vorherige Köpfe genügt deshalb nicht: C2-Entry 1 mit R2-Kopf 0
und R2-Entry 1 mit C2-Kopf 0 hätten keine Vorgängerabhängigkeiten und wären so
scheinbar sortierbar. Tatsächlich behaupten beide, vor dem jeweils anderen
bestätigt worden zu sein, was unter dem gemeinsamen Lock unmöglich ist.

Der lineare Merge beginnt bei C2=0/R2=0 und liest jeweils nur die nächste
Zeile beider eigenen lückenlosen Sequenzströme. Eine Zeile ist auswählbar, wenn
ihr beobachteter Gegenkopf exakt dem bereits geprüften Gegenstrom entspricht.
Bei noch vorhandenen Einträgen muss **genau eine** der beiden nächsten Zeilen
auswählbar sein: Zwei bedeuten die unmögliche gegenseitige Vorherbehauptung,
keine bedeutet einen zukünftigen, veralteten, fehlenden oder zyklischen Bezug.
Nach Prüfung wird nur der gewählte eigene Cursor erhöht. Bei erschöpftem
Gegenstrom muss der verbleibende Kopf weiterhin exakt dessen endgültigem
Cursor entsprechen.

Eigene Sequenzen und beobachtete Köpfe sind strikt Integer, keine booleschen
Werte; Sequenzen beginnen bei 1, beobachtete Köpfe bei 0. Die beobachteten
Gegenköpfe jedes Stroms sind monoton. Der gemeinsame Lock liefert bei echten
Bestätigungen diese serialisierbare Reihenfolge. Ein alter C2-v1-Entry nach
einem ersten R2-Entry, der noch einen kleineren C2-Kopf beobachtet hat, kann
damit nicht als spätere zulässige positive Buchung eingeschoben werden.

Damit sind keine Zeitstempel als Reihenfolgebeweis und kein zusätzliches
positives Journal nötig. Bestehende C1/R1-Quellen bleiben getrennt geprüft;
ihre beobachteten Sequenzpräfixe werden wie bisher gebunden. Der gemeinsame
Validator darf keine Restorehorizonte oder rekursiven vollständigen
Domänenvalidatoren aufrufen. Module können seine einmalig berechneten
Teilzustände für ihren eigenen Horizon verwenden.

Diese Mergelösung muss vor Implementierung als konkreter
Vertrag geprüft werden. Eine zusätzliche globale Operationsfolge wäre eine
alternative, größere Persistenzlösung; beide Ansätze nicht parallel einführen.

## Aktuelle vollständige Rechte getrennt von Beweisreihenfolge

R2 benötigt aktuelle volle Rechte auf den ganzen Refund, alle bereits
gebundenen und neu gewählten Ursprungsevents sowie sämtliche historisch
getragenen Kapazitätsquellen eines C2-Lots. Globale Lotreste werden weiterhin
ungefiltert berechnet; öffentlich erscheinen nur autorisierte Kandidaten und
opake Aggregate, keine fremden Claims oder versteckten Anzahlen.

Die bisherigen `access_segments_json`-Bindungen bleiben unverändert und werden
für neue C2-Entries weiterhin vollständig aus prior/new-Segmenten gebildet.
Bei neuen Abschnitten müssen Zugriffsleser R1- und R2-Releaseclaims auflösen.
R2-Entries benötigen selbst eine minimale unveränderliche versionierte
Quellen-ID-Bindung, die vor Fachdetails gelesen und anschließend exakt gegen
den vollständig rekonstruierten Proof geprüft wird. Auch unbenutzte, im
gespeicherten Gruppenstand enthaltene Quellen bleiben relevant.

Der Autorisierungsgraph kann auf Ebene ganzer aktueller Events trotz korrekter
Eintragschronologie einen Kreis enthalten: Ein Refundevent hat Portionen für
Rechnungen A und B. Seine A-Portion wird zuerst gebunden. Ein späterer
Einnahmen-CashEvent mit ebenfalls A- und B-Portion dokumentiert A aus diesen
Rücknahmecents und B aus anderer schon vorhandener Kapazität. Die noch offene
B-Refundportion kann anschließend den neuen B-Lot desselben Einnahmen-Events
zurücknehmen. Die Rechnungsbindungen sind korrekt; der vollständige aktuelle
Eventzugriff führt aber über dessen A-Aufteilung zurück zum Refundevent.
Gleiche CashDates sind zulässig. Deshalb keine rekursiven
`R2._access ↔ C2._access`-Aufrufe verwenden.

Stattdessen zuerst eine endliche relationale Quellenhülle mit typisierten IDs
und visited-Menge bilden, dann alle ganzen CashEvent-Quellrechte frisch prüfen,
danach Fachdetails/Beweise ausgeben. Die Hülle umfasst vollständige aktuelle
Refundbindungen über beide Versionen sowie die historisch tatsächlich
gebundenen C2-Abschnitte und deren Ursprünge. Das ist von der azyklischen
chronologischen Eintragsprüfung getrennt. Ein späterer Rechteverlust versteckt
den ganzen betroffenen Stand und sperrt auch Replay.

## Vorgeschlagene API und additive Tabellen

Neue Fachroute unter bestehender Transportbasis:
`/api/v1/business/accounting/refunds/v2/events/{event_id}` mit State, Portions,
Origins, History, Preview und Confirm. Neues Feature additiv; R1 bleibt lesbar.
Der neue State summiert dokumentierte R1+R2-Portionen, die neue History enthält
nur R2-Entries. R1-History wird separat unverändert geladen. Writer/Action je
Portion unterscheiden sinngemäß alte Bindung, erste gemeinsame R2-Übernahme
und weitere R2-Bindung. Technische Versionsnamen gehören nicht in Produkttexte.

Originwahl und neue Linien tragen origin_version. Eine Vorschau bindet die
ganze ursprüngliche Refundportion, gemischte konkrete Lotliste, volle
Versionsidentitäten, unveränderte Lotbasis, globalen kumulativen R1+R2-Stand,
Rechnungsübernahmestand und beobachteten C2-Kopf. Beträge werden nicht automatisch
aus gleichen Summen oder ähnlichen Daten gewählt.

Vorschlag für ein neues additives Modul mit fünf eigenen Tabellen:

1. Einmalige R2-Rechnungsübernahmen mit dem ersten R2-Entry und festen R1-Claims.
2. R2-Entries mit eigener globaler Sequenz/Eventrevision, ganzen Allocation-/
   Portionclaims, kanonischer Antwort, Proof und minimaler Zugriffs-ID-Bindung.
3. R2-Linien mit versioniertem Ursprung und festen Rücknahme-/Vorher-/Nachhercents.
   Zwei getrennte nullable C1-/C2-Ursprungsschlüssel mit CHECK auf genau einen
   passenden Zweig erlauben echte zusammengesetzte FKs auf beide alten
   Linientabellen; kein ungeprüfter polymorpher Roh-ID-Verweis.
4. Unveränderliche R2-Requestquittungen für exakt originale Nutzlasten.
5. R2-Releaseclaims mit FK auf R2-Linie und bestehenden C2-Abschnitt.

Namen, exakte Spalten, DTOs und Proofschemata bleiben dem späteren Vertrag
vorbehalten. Alle neuen Tabellen brauchen die bestehenden SQLite-/PG-
Unveränderlichkeitsregeln. Keine Änderung alter Modul-DDL oder Guards.

## Pending, Teilinstallation und Restore

Ein gemeinsamer logischer Refund-Event-Pendingschlüssel umfasst beide
Refundpfade. Gespeicherter Pfad, Body, Versionskennungen und Request-ID bleiben
unverändert. Alte angenommene R1-Requests müssen nach frischen Sicherheitsgates
vor der neuen Writersperre exakt zurückkommen. Ein sicher nicht angenommener
Request darf nach Receiptprüfung, vor Schreibwirkungen, den vorhandenen
strukturierten 409/not_accepted-Hinweis verwenden.

Die in 3b eng auf Komponenten begrenzte Pendingbehandlung wird dafür gezielt
auf die beiden Refund-Confirmrouten erweitert, ohne andere Vorgangsarten zu
ändern. Unmarkierte 409, Rechte-/Betriebssperren und unklare Übertragung erhalten
den ursprünglichen Auftrag; keine automatische Pfad-/Versionsumschreibung.
Alte gespeicherte Details werden vor vollständiger aktueller Autorisierung
nicht angezeigt. R1-Quittungen und Antworten werden nicht neu geschrieben.

Die Erweiterung gilt nur als nicht installiert, wenn sämtliche neuen Tabellen
und ihr Marker fehlen und keine neuen Proofreferenzen existieren. Jede
Teilinstallation oder fehlende Abhängigkeit ist ein Fehler, kein Rückfall auf
R1 oder auf C2-Proofschema 1. Nach bestehender Rechnungsübernahme darf auch ein
deaktiviertes neues Clientfeature den alten R1-Schreiber nicht wieder öffnen.

K1 behält seine bestehenden sechs Tabellen; deren alte Zeilen bleiben
unverändert. Der zusätzliche R2-Teilhorizont bindet alle fünf neuen Tabellen
einschließlich R2-Releaseclaims. Der nächste gemeinsame Horizont
kann H6 mit zusätzlichem refunds_v2-Teil und Operatorberichtschema 7 werden;
das ist ein Vorschlag, keine implementierte Zusage. Alte H1/A1/C1/R1/K1- und
H5/Schema-6-Parser behalten ihre feste Gestalt. Alte erfolgreiche Betreiber-
quittungen entsperren keine neue Wiederherstellung.

## Gezielte spätere Nachweise

Noch nicht ausgeführt:

- Teilweise alter R1-Rücklauf eines C1-Lots, dann R2-Teilbeträge bis zur exakt
  vollständigen Rücknahme ohne Reset des kumulativen Steuercents.
- Ganze gemischte C1+C2-Refundportion, mehrere Lots derselben Gruppe;
  anschließend R2-Cents über unveränderten C2-Pfad wieder belegen und erneut
  über R2 zurücknehmen. Mindestens zwei vollständige neue Zyklen.
- Konkurrierende R1-/R2-Bindung beim Übergang, doppelte Portion, letzter Lotrest
  und doppelte R2-Freigabe; ein Fehler rollt die ganze Mischportion zurück.
- C1-/R1-/C2-Altantworten und alte Proofs bleiben unverändert; neue Source-
  oder Kandidatenstände werden nicht auf erfolgreiche historische Replays
  angewandt. Teilinstallation und abgeschaltetes Feature öffnen keinen alten
  Schreiber.
- Vorwärtsbezug, gefälschte Gegenköpfe, fehlende Präfixzeile und Zyklus werden
  auch bei konsistent neu berechneten lokalen Hashes abgewiesen.
- Historische Mehrgruppen-Zugriffsmengen, später erweiterte vollständige
  Quellumfänge und ein gültiger Event-Autorisierungskreis werden sicher und
  endlich behandelt; keine Details vor vollständiger aktueller Autorisierung.
- Unknown Finance-Refund vor Import, falsches CashDate, verlorene Antwort,
  Restore-/Rechtewechsel zwischen Preflight und Retry, SQLite-/PG-Schutz und
  neuer vollständiger Restorehorizont; unveränderte OP-/Paymentwirkungen.
