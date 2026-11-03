# Neuer Gesamtfall v5 – unabhängiger Zwischenstand

Stand03.11.2026. Acht eigene Gegenproben des reinen Gesamtfallrechners bestehen.
Die tatsächliche private API und die atomaren Abschlussnachweise werden noch
integriert; dieser Bericht ist keine vollständige v5-Abnahme.

Geprüft sind tatsächliche16-Tage-Teilmonatsgrenzen mit getrennten KV-/RV-Basen,
ein steuerfreier Reisebetrag ohne zweite Lohnzahlung oder Arbeitgeberkosten,
die Centbilanz aus laufendem Entgelt, individueller Erstattung, Sachbezug und
abgewälzter Pauschalsteuer, sowie ein ganzer unbezahlter Monat ohne erfundene
SV-Tage und ohne verkürzten steuerlichen Monatszeitraum.

Fremde Reisequellen werden auch mit neu berechnetem Adapterhash zurückgewiesen.
Verschiedene Reiseabrechnungen können dieselbe Betragszuordnung nicht doppelt
verwenden. Ein beliebig geänderter Pauschalsteuerbetrag wird neu berechnet und
abgewiesen. Ein erster bereinigter Review fand, dass `true` oder`1.0` in den
gespeicherten Versionsfeldern als Ganzzahlversion1 akzeptiert wurden; die
Snapshot- und Reiseadapterversionen verlangen jetzt ausdrücklich Integer.

Die erste Testdateifassung enthielt zusätzlich eigene Fixturefehler: eine
versehentlich identische statt fremde Personen-ID, eine Versicherungsprognose
außerhalb des unterstützten Pflichtversicherungszweigs und eine unzutreffende
Cent-Rundungserwartung. Diese wurden vor der isolierten Fehlermeldung korrigiert;
sie werden nicht als Produktfehler gezählt.

[Unabhängige Tests](../backend/test_payroll_calculations_review.py),
[ausgeführter Endlauf](evidence/payroll-calculations-review-2026-11-03.txt),
[Quellhashes und Integrationsnachweis](evidence/payroll-claims-integration-review-2026-11-03.json).
