# P4 – unabhängige Prüfung von Anspruchskern und privaten Quellen

Stand: 03.11.2026. **Neun eigene reine Grenzprüfungen sowie acht zusätzliche
Prüfungen der privaten Quellen bestehen.** Die vollständige Zusammenrechnung
im Lohnlauf und beide neuen Anspruchsoberflächen sind damit noch nicht
abgenommen.

## Unabhängige Quellenbasis

- [AOK, Dauer der Entgeltfortzahlung](https://www.aok.de/fk/sozialversicherung/entgeltfortzahlung-und-ausgleichsverfahren/dauer-der-entgeltfortzahlung/),
  Seitenstand 29.06.2026, am 03.11.2026 erfolgreich als vollständige HTML-Seite
  gelesen. Besonders geprüft: Beginn und Wartezeit, getrennte Erkrankungen,
  Sechsmonatsrückblick und neuer Zwölfmonatsbeginn nach erneuerter Berechtigung.
- [BUrlG §11](https://www.gesetze-im-internet.de/burlg/__11.html),
  am 03.11.2026 erfolgreich vollständig gelesen: 13-Wochen-Referenz,
  Überstundenabgrenzung, dauerhaft erhöhte Vergütung, geschützte Minderungen
  und Ausgleich entfallender Sachbezüge.

Die Erwartungswerte wurden unabhängig von den geprüften Funktionen festgelegt.
Der Drei-Tage-Wochenfall verwendet 39 Referenzarbeitstage und den exakten
Bruch 390049/39 für drei Urlaubstage; zuzüglich drei Sachbezugsersatzbeträgen
zu je199 Cent ergibt sich nach einmaliger Rundung30601 Cent.

## Abgedeckte Gegenproben

1. Neuer Anspruch nach sechs Monaten setzt auch den Zwölfmonatsanker neu.
2. Rückblick über Augustende und kurzen Februar unterscheidet 28.02./01.03.
3. Vier Wochen Wartezeit verbrauchen keine bezahlten Sechswochentage.
4. Andere belegte Krankheitsursache erneuert nicht den alten Krankheitsanspruch.
5. Ungeklärte Genesung oder ungeklärtes Verschulden erzeugt keinen Anspruch.
6. Unbezahlter Monat ab31.01. endet28.02. und hat29 tatsächliche Kalendertage.
7. Urlaubsentgelt einer Drei-Tage-Woche rundet erst den Gesamtbetrag;
   tatsächliche Projektarbeit bleibt unverändert.
8. Feiertagsentgelt verlangt Anspruch und alleinigen Ausfallgrund.
9. Unbekannte gespeicherte Regelversion wird nicht durch die aktuelle ersetzt.

[Testcode](../backend/test_payroll_entitlements_review.py),
[ausgeführtes Protokoll](evidence/payroll-entitlements-review-2026-11-03.txt).

## Weiter erforderliche Prüfung

Die privaten Gegenproben rekonstruieren Ansprüche aus tatsächlichen
personengebundenen Originalen: manipulierte Stundenvereinbarung, verlängerter
Sollplan, ausgetauschte Dateimetadaten und verändertes Anspruchsfenster werden
auch bei konsistent neu berechnetem Plan, Hash und Quittungsbezug abgewiesen.
Ein tatsächlicher Urlaubsnachweis kann nicht als Krankheit bezahlt werden.
Entzogene Freigaberechte sperren auch den unveränderten Lost-ACK-Replay;
korrigierte Vorzeiten erhalten den alten angenommenen Anspruch, sperren aber
seine ungeprüfte neue Verwendung.

Eine erste Gegenprobe fand eine Lücke: Eine später tatsächlich vorhandene,
identisch projizierte Mitarbeiterrevision konnte nach vollständiger Neuberechnung
der Hashwerte als ursprünglicher Stand erscheinen. Die Speicherung bindet nun
den unveränderten ursprünglichen Auftrag privat an den Annahmehash und die
Quittung. Er wird nicht an die Oberfläche ausgegeben. Auch Restore prüft diese
Bindung. Der unabhängige Endlauf bestand mit acht von acht Fällen in2,057s.

[Testcode der privaten Gegenprüfung](../backend/test_business_payroll_entitlements_review.py),
[Endlauf](evidence/payroll-entitlements-private-review-2026-11-03.txt),
[Quellhashes und getrennte Integrationsläufe](evidence/payroll-claims-integration-review-2026-11-03.json).

Zusammentreffen von Monatslohn/Anspruchslohn, mehreren Anspruchsarten und
Reiselohn darf keine doppelte Vergütung erzeugen. Überlappende Ursachen,
Abrufarbeit und weitere noch nicht unterstützte Fälle bleiben echte
Entwicklungsaufgaben. Diese Prüfung behauptet keine vollständige
Lohnabrechnung oder fachliche Produktivfreigabe.
