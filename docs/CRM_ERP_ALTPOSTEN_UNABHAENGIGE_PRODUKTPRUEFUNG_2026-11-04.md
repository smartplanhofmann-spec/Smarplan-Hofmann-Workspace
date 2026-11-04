# Offene Altposten – unabhängige Produktgegenprüfung

04.11.2026, isolierter Arbeitsbaum `/workspace/smartplan-opening-items-20261104`.
Reine Prüfung mit eigener Testdatei; keine Produktdatei verändert, kein Commit,
kein PostgreSQL- oder Produktivkontakt. Gelesen wurden der tatsächliche neue
Domain-/Quellen-/Rechenkern, die EÜR-/Bank-/Liquiditätsanschlüsse und der additive
APIvertrag. Die amtliche Quellengegenprüfung ist separat dokumentiert in
`CRM_ERP_ALTPOSTEN_QUELLEN_GEGENPRUEFUNG_2026-11-04.md`; ihre engen Voraussetzungen
werden nicht zu einer pauschalen steuerlichen Zulassung erweitert.

**Ergebnis: zehn eigene tatsächliche Workflowfälle bestanden, 5,447 Sekunden.**
Testdatei `backend/test_accounting_open_items_independent_review.py`. Die
Testdatenbank enthält ausschließlich synthetische Originale, alte Centanteile,
tatsächliche Domainannahmen und selbst erzeugte Bankauszüge. Gemeinsame
Fixturehelfer bereiten Belege vor; die Sollbeträge sind unabhängig vorgegebene
Referenzwerte, keine nachgebaute Produktformel.

| Gegenfall | Belegtes Verhalten |
|---|---|
| Original 100/19/119, alte Zahlung 39,67 | Tatsächlich belegte 33,33/6,34 werden nicht still zu 33,34/6,33 umgerechnet, sondern mit 409 gesperrt. Unterstützte alte 33,34/6,33 bleiben in Originalannahme erhalten; neue Anteile 33,33/6,34 und 33,33/6,33 verbrauchen den Rest vollständig. |
| Lieferant 1.000/190/1.190, alt 238 bezahlt, alte Vorsteuer 190 abgezogen | Neue 357 und595 erzeugen EÜR 300+57 und 500+95, insgesamt 952 Ausgabe. Neuer Vorsteuerabzug 0; keine erfundene Finanzamtserstattung. |
| Früherer erklärter Voranmeldungsmonat ohne rechtzeitige Ausübung | Abzugstag am/nach Beginn oder vor Anspruchsentstehung wird 409 abgewiesen; unvollständiger alter Abzug ebenfalls. |
| Softwarebeginn01.11., gleiche Jahreshälfte bereits bezahlt | Alte 59,50 werden nicht erneut gebucht. Tatsächliche Zahlung 01.11. wird vollständig neu verarbeitet, 31.10. gesperrt. `partial_period_profile_coverage` bleibt bestehen und `euer_surplus` bleibt unbekannt. |
| Neue tatsächliche Zahlung ohne EÜR-Zuordnung | Geldbewegung bleibt sichtbar und erhöht den berechneten Bestand 1000 → 1059,50. Umsatz/USt werden nicht erfunden; fehlende Klassifizierung bleibt ausdrückliches Problem. |
| Zahlung mit EÜR und realer Bankzuordnung aufheben | Zuerst echte Gegenbuchung, dann echte leere neue Bankzuordnung nötig. Erst danach ist Void zulässig. Alte Zahlungsquelle/Originalannahme/Historie bleiben abrufbar. |
| Original- oder Zahlungsannahmequittung kontrolliert entfernt | Livebestand, Originalreplay, Geldquelle und Integrität verweigern den beschädigten Bestand. Nach Rollback der Testmanipulation sind Originalbytes und Annahme exakt wieder vorhanden. |
| Export nach tatsächlicher Zahlung, später Gegenbuchung undVoid | Ursprünglicher Export bleibt vollständig gleich; aktueller Erlös geht auf 0 zurück. |
| Forderungszahlungen über zwei Kalenderjahre | Je 595 tatsächlich in 2026 und 2027 bedeutet je 595 EÜR-Einnahme und 95 Ist-USt; kein neuer Vorsteueranspruch. Der zuvor eingefrorene Export für 2026 bleibt gleich. |
| Frühere Teilzahlung korrigieren, spätere Rate existiert | 409 bis spätere Rate ausdrücklich aufgehoben ist. Anschließender Rest 79,33 bleibt 66,66 Netto / 12,67 Steuer, alte Quellen bewahren ihre tatsächlichen Centanteile 6,34 / 6,33. |

Der erste Lauf hatte sieben grüne Fälle und einen Fehler ausschließlich in
meiner Assertion: Ich verwendete `recorded_balance` statt des tatsächlichen
Liquiditätsfeldes `calculated_balance`. Der finale Test benutzt den echten
DTO-Namen; Erwartungsbetrag und fachliche Aussage wurden nicht geändert. Der
erste Log bleibt erhalten und wird nicht als Produktfehler ausgegeben.

Keine offenen reproduzierten Produktbefunde in diesem geprüften Stand. Dies ist
keine Abnahme weiterer Steuergruppen, anderer alter Rundungsverfahren, später
korrigierter Vorsteueransprüche, Gutschriften/Skonti/Rückzahlungen oder einer
vollständigen Jahresübernahme. Keine Aussage zu noch laufender Client- oder
PostgreSQL-Abnahme. Dateihashes und beide unveränderten Logs stehen im
Evidenzmanifest `docs/evidence/opening-items-independent-2026-11-04/manifest.json`.
