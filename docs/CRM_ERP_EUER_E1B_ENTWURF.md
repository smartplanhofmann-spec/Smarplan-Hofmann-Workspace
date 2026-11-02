# E1b-Entwurf: Quellenzuordnung und belegte Betragsaufteilung

Stand: 02.11.2026. **Plan, noch keine Umsetzung.** Rein lesende Prüfung des
aktuellen E1a-Quellcodes; keine neuen Produktfunktionen oder Datenbankänderungen
für diesen Entwurf. Grundlage sind der [EÜR-Plan](CRM_ERP_EUER_PLAN.md) und der
[E1a-Vertrag](CRM_ERP_EUER_E1A_API.md).

## 1. Offene Angaben und klarer Umfang

Bestätigt ist ausschließlich **Einzelunternehmen mit EÜR**. Kleinunternehmer-
oder Regelbesteuerung, gegebenenfalls Soll-/Istbesteuerung samt Gültigkeit,
Buchhaltungsbeginn und fachliche Konten-/Kategorienzuordnung sind offen.
Vorhandene Rechnungssteuersätze beantworten diese Fragen nicht. Insbesondere
begründet EÜR keine automatische Istbesteuerung.

Der kleinste jetzt umsetzbare E1b-Abschnitt ist eine **belegte Quellenzuordnung
mit dokumentarischer Betragsaufteilung**:

- Einen vorhandenen bestätigten Geldfluss vollständig oder teilweise festen
  Ausgangsrechnungen zuordnen; unbekannter Rest bleibt ausdrücklich ungeklärt.
- Eine bereits vorhandene Zuordnung aus E1a/Finance übernehmen, ohne den
  Geldfluss oder dieselbe Rechnungswirkung erneut anzulegen.
- Aus unveränderten Belegen die ausgewiesenen Netto-/Steuerbestandteile eines
  bestätigten Bruttoanteils nachvollziehbar verteilen. Das sind Beleganteile,
  keine berechnete Umsatzsteuerperiode oder bestätigter Vorsteuerabzug.
- Vorhandene tatsächliche Kundenerstattungen ausdrücklich passenden
  ursprünglichen Einnahmenteilen zuordnen; ungeklärter Ursprung bleibt offen.
- Eine versionierte sachliche Einordnung mit Begründung speichern, zunächst
  etwa `customer_payment`, `supplier_payment`, `customer_refund`, `unresolved`.
  Diese Kennungen beschreiben den Quellenvorgang; sie sind keine EÜR-Zeilen,
  Steuerschlüssel oder Entscheidung über betriebliche Abziehbarkeit.

`tax_status:'unconfigured'`, `tax_result_available:false` und
`tax_profile_unconfigured` bleiben erhalten. Quellenzuordnung und sachliche
Einordnung dürfen vollständig sein, während steuerliche Freigabe weiterhin
offen ist. Dafür getrennte Zustandsfelder verwenden; kein mehrdeutiges
`booked`/`approved`, das eine steuerliche Freigabe suggeriert.

Zum ersten unterstützten Ablauf gehören gewöhnliche positive EUR-Rechnungen
ohne Abschlags-/Schlussrechnungskette, Skonto, Stornobeziehung oder nachträgliche
Entgeltänderung. Andere Quellen bleiben lesbar und als Klärungsfall erhalten.
Anlagen, Privatanteile, Jahreswechsel, Reverse Charge, steuerfreie Umsätze und
andere Sonderfälle erhalten keine geschätzte steuerliche Behandlung. Eine
vorhandene Belegkategorie `Z`, `E` oder `AE` kann unverändert angezeigt werden;
das erzeugt keine neue Steuerentscheidung.

## 2. Tatsächliche Anschlussstellen

| Bestand | Bedeutung für E1b |
| --- | --- |
| `business_accounting.Accounting.payment_sources`, `receipt_sources`, `events`, `event` | Autorisierte vollständige Quellen, Original-/Archivprüfungen, feste CashEvents. `import_payment`/`payout` bleiben die einzigen Geldflusserfassungen; Zuordnung erzeugt keine neue Zahlung. |
| `business_accounting._payment_source`, `_event` | Der E1a-Hash bindet die **vollständigen ursprünglichen** `business_payment_allocations` sowie finale Archivhashes. Diese Quellenbeweise und gespeicherten E1a-Antworten müssen unverändert bleiben. |
| `business_finance.Finance.record_payment` | Erfasst heute `receipt`/`refund` und anfängliche Rechnungszuordnungen. `reverses` wird immer `NULL`; ein Refund besitzt deshalb noch keinen eindeutigen Ursprung. Es gibt keine öffentliche nachträgliche Zuordnungsoperation. |
| `Finance._payment_sum`, `_item`, `payments`, `open_items` | Berechnen bezahlte/offene Beträge ausschließlich aus den alten Allocation-Zeilen. Refunds mindern bereits die Rechnungszahlung. Eine Gutschrift ist separat in `credited` enthalten. |
| `Finance.record_payment` bei Refunds | Prüft den derzeit bezahlten Rechnungsbetrag. Dieser Pfad muss dieselbe neue effektive Zuordnung lesen wie OP/Mahnen; sonst entstehen widersprüchliche Budgets. |
| `business_documents.calculate_positions`, finale Archiv-Payload | Enthalten `totals.tax_breakdown` mit `rate,category,reason,net,tax`; Positionsrabatte und Preisbasismengen sind bereits berücksichtigt. E1b verwendet den eingefrorenen Gesamtgruppenstand, keine Neuberechnung aus aktuellen Artikeln. |
| `Documents._prior_snapshot` | Kumulative/Schlussrechnungen enthalten inkrementelle `totals` und zusätzlich `contract_totals`. Beide zu summieren würde Quellen doppelt zählen. Ketten zunächst ausdrücklich sperren, bis ein eigener Referenzfall umgesetzt ist. |
| `Finance.receipt`, `review_receipt`, `receipt_original` | Eingangsprüfungen enthalten nur Gesamt-Netto/Steuer/Brutto, keine verlässlichen einzelnen Steuergruppen. Aus ihrem Quotienten darf kein Steuersatz geraten werden. Original und konkrete Prüfversion bleiben die Quelle. |
| `business_adapters.export_data` | Ein bestehender Export verwendet `Finance.payments`; die effektive Zuordnung muss konsistent einfließen. Bereits gespeicherte Exportartefakte bleiben unverändert. E1b erklärt keines der bisherigen Profile zum EÜR-/DATEV-Export. |
| `business_schema.reconcile_financial_restore`, `business_accounting.restore_horizon` | Bestehende Operator-/Restore-Sperre und Nachweis zusätzlicher Buchhaltungsstände müssen auch die neuen Zuordnungszeilen erfassen. |

**Wichtige Integrationsgrenze:** Auch ein bloßes zusätzliches `INSERT` in
`business_payment_allocations` für eine bereits importierte Zahlung würde den
alten E1a-Quellenhash verändern. E1b benötigt deshalb ein neues anhängendes
Zuordnungsjournal; alte Allocation-Zeilen bleiben unverändert.

## 3. Ein gemeinsamer effektiver Zuordnungsstand

Eine neue zentrale lesende Projektion bildet je Zahlungs-ID:

`ursprüngliche Finance-Zuordnungen + bestätigte zusätzliche E1b-Zuordnungen`.

Ursprüngliche Zeilen werden nur referenziert und genau einmal berücksichtigt.
E1a-Quellenbeweis und Snapshot bleiben die historische Basis; die neue
effektive Projektion wird separat mit eigener Revision und eigenem Hash
ausgegeben. Eine spätere Einordnung verändert auch nicht die gespeicherte
E1a-Wiederholungsantwort mit `classification_status:'unclassified'`.

Die Projektion muss gemeinsam verwendet werden durch Zahlungslisten/
unzugeordneten Rest, `_payment_sum`, OP, Mahnbeträge, Refund-Budgetprüfung und
die daraus erzeugten neuen Export-Snapshots. Direkte Finance-Zahlungserfassung
bleibt möglich; sie muss den effektiven Rechnungsstand unter derselben
Datenbanktransaktion prüfen. Eine zweite Schattenrechnung nur in Accounting
ist keine vollständige Quellenzuordnung.

Vorgeschlagene neue unveränderliche Daten:

- Zuordnungsereignis mit CashEvent-/Payment-ID, erwarteter Revision,
  vollständigem Quellenhash, Akteur, Zeitpunkt, Anfrage-ID und Bestätigungsgrund.
- Zeilen mit unverändertem Beleg-ID/Revision/Payload-/PDF-Hash, positivem
  Brutto-Centbetrag, Referenz auf vorhandene Basiszuordnung oder neuen
  zusätzlichen Anteil und gegebenenfalls Ursprung einer Erstattung.
- Sachliche Einordnung und dokumentarische Komponenten als eigene Version mit
  Regelkennung, Quellen-/Prüfversion und expliziter Steuerfreigabe `unconfigured`.

Der genaue Tabellen-/API-Vertrag wird vor der Umsetzung technisch festgelegt.
Ein mögliches kleines API-Paket besteht aus einer lesenden effektiven
Zuordnungsansicht, einer nebenwirkungsfreien Vorschau und einer ausdrücklichen
Bestätigung je CashEvent. Vorschau und Bestätigung binden Quellen-, Zuordnungs-
und Beleggruppenstände; eine Bestätigung mit veraltetem Stand liefert 409.

Zusätzliche Zuordnungen sind anfangs nur additive Verteilungen bisher freien
Betrags. Falsche bestätigte Zuordnungen werden nicht überschrieben. Eine
begründete Aufhebung/Ersetzung benötigt den vorgesehenen E1c-Korrekturpfad;
die Oberfläche muss diese Grenze vor Bestätigung sichtbar machen.

Die Summe aller effektiven Zahlungszuordnungen überschreitet weder den
ursprünglichen Geldfluss noch den jeweils zulässigen offenen Quellenbetrag.
Eine historische Überzuordnung wird erkannt und als Klärungsfall erhalten;
sie wird nicht durch Kürzung vorhandener Zeilen kaschiert. Nicht zugeordneter
Rest ist weder automatisch Gewinn noch neutraler oder steuerfreier Betrag.

## 4. Exakte Centverteilung ohne erfundene Steuerregel

Alle Berechnungen verwenden ganze Cent oder exakte Dezimalzahlen. Die
archivierte Gruppe erhält eine stabile Identität aus Beleg-/Archivbindung und
`rate,category,reason`; heutige Artikel-, Konten- oder Steuereinstellungen sind
keine Rechenquelle.

Bei genau einer positiven Beleggruppe kann die Vorschau den Bruttoanteil
eindeutig dieser Gruppe zuweisen. Bei mehreren Gruppen bestätigt der Anwender
die Bruttoverteilung ausdrücklich. E1b nimmt ohne eigene Regel-/Referenzprüfung
keine automatische proportionale Zuordnung auf mehrere Steuergruppen an.
Die Gruppensummen müssen genau den zugeordneten Brutto-Centbetrag ergeben
und jede Gruppe darf höchstens ihren noch verfügbaren Bruttorest verbrauchen.

Innerhalb einer unveränderten Gruppe mit archivierten Centwerten `N` netto,
`T` ausgewiesener Steuer und `G=N+T>0` wird für den kumulativ bestätigten
Bruttoanteil `C` folgender dokumentarischer Vorschlag eingefroren:

`Steueranteil(C) = ROUND_HALF_UP(C*T/G)`

`Nettoanteil(C) = C - Steueranteil(C)`

Ein neuer Teil erhält jeweils die Differenz zwischen neuem und vorherigem
kumulativem Stand. Dadurch entspricht die vollständige Zahlung exakt den
archivierten Gruppensummen; jede Teilzeile summiert exakt zu ihrem Brutto.
Die Reihenfolge der bestätigten Verteilungen ist Teil des Nachweises; weder
spätere Importe noch rückdatierte Geldflüsse rechnen frühere Anteile neu aus.

Beispiel ausschließlich als Rechenreferenz: Eine Quelle mit 100,00 netto und
19,00 ausgewiesener Steuer wird in 39,67 / 39,67 / 39,66 aufgeteilt. Die
eingefrorenen Netto-/Steueranteile sind 33,34/6,33; 33,33/6,34; 33,33/6,33.
Die Summe bleibt 100,00/19,00. Daraus wird keine Aussage zu einer realen
Umsatzsteuerpflicht oder Periode abgeleitet.

Bei Eingangsbelegen ist dieselbe Aufteilung zunächst nur auf die bestätigten
Gesamtwerte der konkreten Prüfversion möglich. Bezeichnung: „ausgewiesener
Steueranteil laut Prüfung“, niemals automatisch „abziehbare Vorsteuer“.
Einzelne Eingangs-Steuergruppen benötigen zusätzliche explizite Belegdaten;
sie werden nicht aus Gesamtwerten rekonstruiert.

## 5. Erstattungen und geänderte Prüfstände

Ein vorhandener `refund` bleibt ein eigener echter Geldabfluss. E1b kann eine
ausdrücklich bestätigte Beziehung zu einem bereits übernommenen ursprünglichen
Zahlungseingang und dessen konkreten Rechnungs-/Gruppenanteilen hinzufügen.
Weder `reverses` noch der ursprüngliche CashEvent werden dafür geändert.
Währung, berechtigte Parteien-/Rechnungsbindung, Quellenhashes und noch nicht
erstatteter Betrag werden geprüft. Erstattungsanteile dürfen insgesamt weder
den Refund noch die ausgewählten ursprünglichen Anteile überschreiten.

Bereits bestehende Refund-Rechnungszuordnungen wirken heute negativ auf OP.
Die neue Ursprungsbeziehung zählt diese Wirkung nicht nochmals. Bei einer
bislang unzugeordneten Erstattung wird nur die zusätzliche Zuordnungswirkung
in der gemeinsamen Finance-Projektion erfasst. Eine Stornogutschrift erzeugt
für sich allein keinen zweiten Geldabfluss.

Für dokumentarische Teilrücknahmen wird der **eingefrorene ursprüngliche
Anteil** mit seinen Centkomponenten verwendet. Kumulative Rücknahme und
Restcentverfahren müssen bei vollständiger Rücknahme exakt dessen Netto- und
Steueranteile erreichen. Fehlender Ursprung bleibt `refund_origin_unresolved`;
keine automatische Wahl anhand gleicher Beträge oder Datumsnähe.

Eine Rücknahme kann andere Rundungscent freigeben als eine neue Verteilung
vom ursprünglichen Gesamtbrutto aus. Deshalb werden zurückgegebene Netto- und
Steuercent als genaue Restkapazitäten ihrer Quellgruppe weitergeführt. Eine
nachfolgende erneute Einnahme beginnt einen neuen dokumentierten
Verteilungsabschnitt mit diesen Restkapazitäten als `N,T,G`; bisherige
Aufteilungen bleiben unverändert. Der kumulative Stand `C` gilt innerhalb
dieses Abschnitts. Ein vollständig wieder belegter Rest verbraucht genau
dessen freigegebene Komponenten. Ein bloßes Neuverteilen über den saldierten
Gesamtbruttobetrag könnte sonst einen Cent verlieren oder doppelt zuordnen.

Eine spätere Eingangsprüfung verändert alte Geldflüsse und Aufteilungen nicht.
Die alte konkrete Prüfversion bleibt für Anzeige und identische Wiederholung
gültig. Eine neue Auszahlung/Einordnung gegen den geänderten Stand bleibt
zunächst `review_changed` und gesperrt. Ein späterer ausdrücklicher
Review-Abgleich muss beide Versionen und bereits bestätigte Anteile binden;
er gehört nicht als stilles Entsperren in diesen kleinsten Abschnitt.

## 6. Implementierbare Akzeptanzfälle

1. **Nachträgliche Zuordnung:** Vorhandene Zahlung 130,00 mit alter Zuordnung
   59,50 zu einer normalen Rechnung über 119,00. Weitere 59,50 zuordnen;
   anschließend bezahlt 119,00, OP 0,00 und Rest 11,00. Kein zweiter CashEvent,
   keine zweite Zahlung, unveränderte alte Allocation-/E1a-Hashwerte. Zahlungs-
   liste, OP, Mahnvorschau und neuer Adapter-Snapshot stimmen überein.
2. **Ursprüngliche Zuordnung nur einmal:** Eine vollständig zugeordnete Zahlung
   nochmals sachlich einordnen. Der bezahlte Betrag steigt dabei nicht; die
   Einordnung besitzt einen eigenen Beleg und ändert keine alte Antwort.
3. **Restcent:** Obiges Drei-Teil-Beispiel ergibt exakt 100,00/19,00. Replays,
   Neustart und spätere weitere Importe ändern keine bestätigte Teilzeile.
4. **Mehrere Gruppen:** Archivierte Gruppen 100,00+19,00 und 50,00+3,50.
   Ohne ausdrückliche Bruttoaufteilung keine Bestätigung. Mit bestätigten
   Gruppenbeträgen stimmen Zeilen-/Gruppen-/Gesamtsummen; falscher Gruppenhash,
   überzogener Rest oder ein fehlender Cent ergibt 409/400 ohne Teilbuchung.
5. **Erstattung:** Aus einer bestätigten Zahlung 59,50 zunächst 20,00 und dann
   39,50 tatsächlich erstatten und auf dieselben ursprünglichen Anteile binden.
   Die vollständige Rücknahme entspricht exakt dem Ursprung. Eine weitere
   Rücknahme oder konkurrierende Restnutzung scheitert; OP berücksichtigt jede
   bereits vorhandene bzw. neue Zuordnungswirkung genau einmal.
   Zusätzlich den mittleren 39,67-Anteil aus Fall 3 mit dessen tatsächlichen
   634 Steuercent zurücknehmen und später neu bezahlen: Der neu belegte Rest
   erhält wieder 33,33/6,34; die Gesamtsummen bleiben exakt 100,00/19,00.
6. **Ungeklärter Ursprung:** Importierter alter Refund ohne eindeutigen Eingang
   bleibt lesbar und ungeklärt. Das System erfindet weder eine Ursprungs-ID
   noch eine steuerliche Gegenbuchung.
7. **Reviewwechsel:** Geprüftes Eingangsoriginal 119,00, Auszahlung/Aufteilung
   59,50, danach neue Prüfung 142,80 oder 50,00. Alte Bytes, Prüfversion und
   Aufteilung bleiben unverändert; Replay erfolgreich, neue Aktion gesperrt.
   Eine Minderprüfung unter den bereits ausgezahlten Betrag wird nicht durch
   negative neue Auszahlung oder Änderung des Originals ausgeglichen.
8. **Frische Rechte:** Globale Accounting-/Finance-Rechte plus sämtliche
   bisherigen und neu ausgewählten Quellprojekte vor Vorschau, Bestätigung,
   Download und Replay prüfen. Entzug einer einzigen notwendigen Zuordnung
   versteckt den ganzen betroffenen Geldfluss; keine Teilbetragsleckage.
9. **Transaktionen:** Zwei echte PG-Verbindungen verteilen gleichzeitig den
   letzten Zahlungs-/Rechnungs-/Erstattungsrest. Höchstens ein widersprüchlicher
   Auftrag gewinnt. Ausfall nach erster Zuordnungszeile rollt Projektion,
   Einordnungsbeleg, Anfragequittung und Audit vollständig zurück.
10. **Migration und Restore:** Alte Rechnungen, Originale, Zahlungen, E1a-
    CashEvents und vorhandene Exportartefakte bleiben bytegleich. Normale
    Migration verändert keine Geldflüsse. Restore sperrt auch E1b-Schreiber;
    der Operatornachweis bindet die neuen Zuordnungsstände. Die bestehende
    Accounting-v1-DDL/Checksumme wird nicht rückwirkend geändert: neue
    Modulversion/Erweiterung und versionierter Restore-Horizont sind erforderlich.
11. **Ehrlicher Fachstatus:** Mit unkonfiguriertem Steuerprofil sind Quellen-
    zuordnung und dokumentarische Centaufteilung möglich, aber kein steuerlich
    freigegebener Journalposten, Jahresgewinn, Vorsteueranspruch oder Export
    als fertige Anlage EÜR. Nicht unterstützte Rechnungsketten bleiben mit
    konkretem Grund ungeklärt und werden nicht als volle Unternehmenssicht
    ausgegeben.

Die Centregel und fachlichen Zuordnungsschritte benötigen vor Implementierung
einen ausdrücklich eingefrorenen API-/Regelvertrag. Offene Steuerangaben
blockieren diese technische Vorbereitung und Quellenmechanik nicht; sie
bleiben Voraussetzung für die spätere echte steuerliche Klassifikation.
