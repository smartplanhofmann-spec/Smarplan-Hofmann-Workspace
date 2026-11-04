# Unabhängiger Backendreview des Jahresnachweises V2

Datum: 04.11.2026. Prüfbaum: `/workspace/smartplan-year-review-export-carryover-20261104`.

**Neun zusätzliche tatsächliche Fälle bestehen in 7,507 Sekunden. Es wurde kein neuer Produktfehler bestätigt.** Builder, Prüfer, EÜR-Anschluss und tatsächliche Fixture sind gegenüber dem ursprünglichen Ownerhandoff `docs/evidence/year-package-v2-2026-11-04/manifest-before-pg.json` mit SHA-256 `60bcbacd9cfd542442cb2a373d5df6885ca2bee0265966da11d3533f2f946a67` unverändert. Der später ergänzte Owner-PG-Nachweis liegt getrennt in `manifest.json` mit SHA-256 `f3f61ddbca9e2aadfe4189cb21613a86ceb2bede9249700903c7e4e3b1873c02`; dessen Produkt- und Fixturehashes sind identisch. Die neue unabhängige Testdatei ist `backend/test_accounting_year_package_v2_independent_review.py`.

## Tatsächlich geprüfte Fälle

| Fall | Unabhängige Erwartung und Ergebnis |
| --- | --- |
| Alte Zahlung 59,50 EUR, neue Zahlung 59,50 EUR | 119,00 EUR Jahresausgabe, 19,00 EUR historische Vorsteuer; ausschließlich 59,50 EUR neue Geldbewegung. Der unveränderte Anfangssaldo 1.000,00 EUR führt zu 940,50 EUR Liquidität. Alter Aufwand bleibt im August, alte Vorsteuer im Juni. ZIP-Ausgabe erzeugt keine Datenbankänderung. |
| Vorsteuer aus 2025, Lieferantenzahlungen 2026 | Tatsächliches eigenes 2025-Rechnungsoriginal mit alter Vorsteuer und alter/neuer halber Zahlung: 119,00 EUR Aufwand 2026, keine Vorsteuerbuchung 2026, nur 59,50 EUR neue Liquiditätswirkung. Das Archiv enthält unverändert den ursprünglichen Vorsteuerzeitraum 2025-06. |
| Zusätzlicher vollständig bezahlter Altbeleg | Tatsächliche weitere alte Rechnung 119,00 EUR führt zusammen mit der ersten Rechnung zu 238,00 EUR Jahresausgabe und 38,00 EUR historischer Vorsteuer. Aktueller Cash bleibt 59,50 EUR. Geänderte ursprüngliche Journalidentitäten im Archiv scheitern. |
| Drei tatsächliche Jahresvortragsrevisionen | Annahme, Aufhebung und neue Annahme bleiben als Revisionen 1–3 enthalten. Die ursprüngliche Annahme quittiert weiterhin dieselben Daten; das vorher gespeicherte V2-Archiv bleibt bytegleich. Entfernte Aufhebungsrevisionen werden trotz neu berechneter Dateihülle abgewiesen. |
| Gemischter Bericht aus Jahresvortrag und Projektbeleg | Ein einzelnes projektbezogenes Finanzleserecht wird nach einem erfolgreichen Download entzogen. Die globalen Jahresvortragsrechte bleiben tatsächlich gültig; Archiv und Metadaten werden trotzdem mit 403 gesperrt. Das vorher rechtmäßig gespeicherte Archiv bleibt mit seinem ursprünglichen Außenanker prüfbar. |
| Fehlende ursprüngliche Upload-Annahme | Nach gezieltem Verlust einer Quittung in der isolierten Testdatenbank scheitert ein neuer Liveabruf. Das vorher vollständig erzeugte Archiv bleibt unabhängig von dieser heutigen Datenbankänderung mit dem ursprünglichen Archivhash prüfbar. |
| Original- und Quittungsmanipulation | Entferntes eigenständiges Zeitraumjournal sowie gekreuzter Annahmebenutzer scheitern auch nach neuer innerer Dateihülle. |
| Teildeckung | August–Oktober bleibt eine unvollständige Jahresdeckung, der Jahresüberschuss bleibt unbekannt. Nachträgliche behauptete Januar-Deckung und Vollständigkeit werden abgewiesen. |
| Tatsächlicher früherer V1-Export | Nach einer späteren echten Buchführungsprofiländerung und einem neuen Jahresjournalupload sind Format, Manifest und sämtliche alten V1-Archivbytes unverändert. Der V2-Prüfer akzeptiert dieses V1-Archiv nicht als V2. |

## Prüfgrenze und Außenanker

Der V2-Nachtrag bindet zusätzliche tatsächliche Jahresvortragsoriginale. Er behebt nicht rückwirkend die dokumentierte fehlende intrinsische Abhängigkeitsschließung alter Journale. Der Prüfer verlangt weiterhin einen **separat authentisierten Archiv-SHA-256**; fehlender, leerer und falscher Hash scheitern. Erfolgreiche Prüfung liefert weiterhin `intrinsic_dependency_closure=false`.

Die Manipulationsfälle prüfen zwei klar getrennte Erwartungen: Mit dem **unveränderten ursprünglichen Außenanker** scheitert jede veränderte Datei. Zusätzlich werden die ausdrücklich implementierten inneren Strukturprüfungen mit einem hypothetisch durch den Angreifer ersetzten Außenanker geprüft. Das zweite Ergebnis behauptet keine unabhängige Herkunft oder vollständige fachliche Prüfung. Steuergesetze werden vom Archivprüfer nicht neu berechnet.

## Ausführung und Nachweise

```sh
PYTHONPATH=backend:backend/online \
/tmp/smartplan-backend-verified/bin/python -m unittest -v \
  test_accounting_year_package_v2_independent_review
```

Finales Log: `work/verification/year-package-v2-independent-final-backend-2026-11-04.log`. Hashgebundener Nachweis: `docs/evidence/year-package-v2-independent-backend-2026-11-04/manifest.json`.

Der erste Versuch bestand acht Fälle. Ein neunter scheiterte berechtigt, weil die neue Testvorbereitung die unveränderliche Identität einer vorhandenen 2026-Rechnung durch ein 2025-Rechnungsdatum ersetzen wollte. Der endgültige Fall hebt diese unbenutzte Testquelle regulär auf und legt ein eigenständiges echtes 2025-Original an. Ausschließlich die Testvorbereitung wurde korrigiert; Produktcode und Erwartungen zum Vorsteuerjahr blieben unverändert. Das erste Log bleibt archiviert.

Dieser Review enthält keine PostgreSQL-Nutzung, keine Produktänderung, keine Änderung am Hauptprojekt und keinen Commit. Der separate Owner-PG-Nachweis sowie der noch getrennt abzunehmende Browser-/Native-V2-Anschluss werden nicht als eigene Prüfungen gezählt.
