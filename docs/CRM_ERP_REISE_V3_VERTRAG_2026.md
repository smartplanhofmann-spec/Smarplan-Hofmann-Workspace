# Reise-v3 – belegte Programmquoten und Boden-Ortskalender

Stand 03.11.2026. `de_travel_2026_v3` ist nach abgestimmter Backend-,
PostgreSQL-, Browser- und nativer Prüfung der aktive Standard. Die eingefrorenen
Module v1 und v2 werden nicht umgeschrieben. Die konkret unterstützte Methode
und ausdrücklich verbleibenden Fachgrenzen stehen unten; eine Abnahme aller
denkbaren gemischten Reisen oder des gesamten CRM/ERP wird nicht behauptet.

## Eingabe: belegtes gemischtes Veranstaltungsprogramm

Reisedetails können zusätzlich `mixed_assessment` enthalten. Das Objekt ist
optional und fehlt bei rein beruflichen Reisen. Eine vorhandene private Zeit
ohne entsprechende Beurteilung erzeugt weiterhin einen konkreten Fachblocker.
Der Client berechnet keine steuerliche Quote selbst und schlägt keine
gewünschten Ergebnisbeträge vor.

```json
{
  "method": "documented_program_ratio",
  "program_sessions": [
    {
      "id": "11111111111111111111111111111111",
      "from": "2026-02-03T08:00:00+01:00",
      "to": "2026-02-03T12:00:00+01:00",
      "kind": "business",
      "source_file_ids": ["ffffffffffffffffffffffffffffffff"]
    },
    {
      "id": "22222222222222222222222222222222",
      "from": "2026-02-03T13:00:00+01:00",
      "to": "2026-02-03T15:00:00+01:00",
      "kind": "private",
      "source_file_ids": ["ffffffffffffffffffffffffffffffff"]
    }
  ],
  "program_complete": true,
  "cost_allocation_reviewed": true,
  "source_file_ids": ["ffffffffffffffffffffffffffffffff"],
  "review_note": "Vollständiges Veranstaltungsprogramm und getrennte Originalkosten geprüft."
}
```

Alle Objektschlüssel sind verbindlich und keine weiteren zulässig. Zeitpunkte
benötigen einen tatsächlichen UTC-Offset. Die 2–1000 Programmpunkte haben
eindeutige 32-stellige Hex-IDs, liegen vollständig in der tatsächlichen Reise
und überschneiden sich nicht. Berufliche Punkte benötigen einen passenden
tatsächlichen Arbeitsabschnitt und dürfen keine ausdrücklich private Zeit
enthalten. Private Punkte müssen von `private_intervals` vollständig umfasst
sein. Umgekehrt müssen alle ausdrücklich privaten Zeiten im Programm enthalten
sein; eine zusätzlich angehängte Urlaubsverlängerung darf nicht verschwinden.
Normale Ruhezeit wird nicht automatisch als privates Programm gewertet.

Originaldateilisten enthalten jeweils 1–100 eindeutige IDs. Die API löst jede
Datei anhand derselben privaten Personalaktenrechte, tatsächlichen Originale
und unveränderlichen Prüfsummen auf wie Mahlzeiten- und Beförderungsbelege.
Sämtliche Programmdateien gehören in `trip.sources.files`, einschließlich der
zusätzlichen Originale einzelner Programmpunkte. Der Vermerk umfasst 1–2000
Zeichen. Beide Prüfbestätigungen werden bewusst durch den Anwender gesetzt;
`false` lässt einen Entwurf zu, verhindert aber die Freigabe.

## Ergebnis und Historie

Die bisherigen Betragsfelder bleiben erhalten. Jeder v3-Tag ergänzt:

```json
{
  "unapportioned_base_minor": 1400,
  "business_share": {"numerator": 2, "denominator": 3},
  "base_minor": 933,
  "meal_reduction_minor": 560,
  "meal_allowance_minor": 373
}
```

`base_minor` ist der berufliche Anteil vor der Mahlzeitenkürzung. Erst dessen
Berechnung wird auf den letzten Cent kaufmännisch gerundet; die anschließende
Kürzung verwendet weiter den vollen gesetzlichen Tagessatz. Reine berufliche
Reisen haben Quote 1/1. Die vorhandene steuerpflichtige 25-%-Grenze verwendet
ebenfalls den tatsächlich beruflichen Pauschalenbetrag vor Mahlzeitenkürzung.
Übernachtungspauschalen werden auf den belegten beruflichen Anteil begrenzt.
Tatsächliche Originalkosten verwenden ihre bereits getrennt geprüfte
`expense_allocations`-Zuordnung; sie werden nicht nochmals pauschal multipliziert.

Die Berechnung ergänzt die Arrays `ground_calendar_sources` und
`mixed_program_sources`. Letzteres bindet Reise-ID/Revision/Hash, tatsächliche
berufliche/private Programmsekunden, gekürzten rationalen Anteil,
Originaldatei-IDs, Methoden-/Modulhash und vollständigen Faktenhash. Beim
Speichern der Abrechnung bleiben beide Arrays erhalten. Historische
Rekonstruktion wählt genau die ursprünglich gespeicherte Regelversion. Neue
Fassungen dürfen niemals alte v1-/v2-Ergebnisse stillschweigend ersetzen.
Das v3-PDF zeigt bei einer gemischten Reise auch Programmquote, ungeteilte
Pauschale, beruflichen Anteil und Mahlzeitenkürzung. Ein tatsächlich erzeugter
und anschließend ausgelesener PDF-Nachweis steht unter
`docs/evidence/travel-v3-program-share-pdf-2026-11-03.txt`.

Der Bodenkalender verwendet unveränderte Reise-/Stättenfelder. Tatsächliche
UTC-Zeitabschnitte werden anhand der Ortszeitzone jedes belegten Abschnitts
örtlichen Kalendertagen zugeordnet. Jede verstrichene Sekunde wird genau einmal
gezählt. Flug- und Schiffsfakten behalten ihren eigenen bestehenden Nachweis.

## Fachliche Quelle, ausgeführte Prüfungen und Grenzen

[BMF 25.11.2020, Rz. 90 und Beispiel 59](https://www.ihk.de/blueprint/servlet/resource/blob/5260010/6167648501baf85de6053f701b93e9b5/bmf-schreiben-25-11-2020-data.pdf)
verlangt die berufliche Aufteilung vor der vollen Mahlzeitenkürzung. Der
unabhängig aus dem veröffentlichten Beispiel formulierte Siebentagestest ergibt
bei 50 % beruflichem Programm insgesamt 1,40 EUR. Ein weiterer Kontrollfall
ergibt aus 28 EUR × 2/3 minus 11,20 EUR einen Tagesbetrag von 7,47 EUR.

17 isolierte Fachtests bestanden am 03.11.2026: 13 Programmquoten- und 4
Bodenkalenderfälle. Negativfälle prüfen fehlende/unvollständige Belege,
überlappende Punkte, private Zeit als Arbeit, doppelte IDs, fehlende
Prüfbestätigungen, nicht zugeordnete Urlaubszeit, Originalbindung und
unveränderte historische v2-Blocker. Log:
`docs/evidence/travel-v3-focused-2026-11-03.txt`.

Die additive Serviceanbindung löst neue Programmoriginale bereits geschützt
auf. Sechs gezielte Servicefälle und zwei echte MFA-/HTTP-Fälle bestanden in
2,434 Sekunden. Sie prüfen Katalog-/Berechnungshashgleichheit, private und
fehlende Originale, ausdrücklich falsche Null-Eingabe, unveränderliche
v3-Historie nach Rückwechsel des Defaults, eine tatsächliche dokumentierte
Zahlung von 9,33 EUR sowie Manipulation eines anschließend neu gehashten
Quotenergebnisses. Die V3-Aktivierung wird dabei nur im Test gesetzt; der
Produktstandard war zu diesem Prüfzeitpunkt noch v2. Nachweis:
`docs/evidence/travel-v3-service-http-2026-11-03.txt`.

Eine unabhängige Gegenprüfung bestand mit acht zusätzlich formulierten Fällen:
veröffentlichtes BMF-Beispiel, volle Mahlzeitenkürzung nach Quote, Centgrenzen
der 25-%-Bemessungsgrenze, zwei Kurzreisen mit gleicher Quote ohne doppelte
Tagespauschale, keine Umdeutung von Unterkunftsüberschuss in Verpflegung,
23-/25-Stunden-Tage, westwärts wiederholtes Datum und unveränderte Delegation
an v1/v2. Es gab keinen bestätigten Fehlerbefund. Die Reichweite dieser Prüfung
ist ausdrücklich der reine Rechenkern, keine vollständige Produktfreigabe.
Nachweis: `docs/evidence/travel-v3-independent-review-2026-11-03.json`.

`web/office/tests/travel_v3_fixture.py` erzeugt
`app/test/fixtures/travel_allowances_v3.json` aus tatsächlichen synthetischen
Fachbefehlen. Enthalten sind Programmoriginal, Entwurf und Einreichung,
getrennte tatsächliche Auslagen, Vorschau und Freigabe, 10-EUR-Zahlung sowie
zwei echte Abrechnungsfassungen nach einer dokumentierten Korrektur. Die
ursprünglichen Exportbytes bleiben unverändert. Die Clientprüfung kann damit
denselben nachweislich erzeugten Vertrag verwenden.

Der echte PostgreSQL-Lauf mit allen fünf Reisefällen bestand in 21,590 Sekunden.
Neben den bisherigen Parallelitäts-, MFA-, Rollen- und Migrationsfällen prüft
er ein v3-Programm, tatsächliche dokumentierte Zahlung von 9,33 EUR sowie echten
Dump/Restore bei v2 als aktuellem Standard. Private Originaldatei, historischer
JSON-Export, Quittung und öffentliche Finanzquelle bleiben unverändert.
Nachweis: `docs/evidence/travel-v3-postgres-final-2026-11-03.txt`.

Dieser Lauf fand zunächst einen bestehenden Fehler im gemeinsamen HTTP-Adapter:
archivierte JSON-Downloadbytes wurden an `jsonify` übergeben und erzeugten HTTP
500. Der minimale Fix sendet `BinaryAttachment` mit unveränderten Bytes, MIME
und Dateinamen. Ein eigener echter MFA-/HTTP-Test reproduzierte den Fehler und
prüft nach dem Fix zusätzlich Größe und SHA256 des archivierten Originals.
Alle drei Reise-HTTP-Fälle bestanden anschließend in 1,230 Sekunden. Die ersten
fehlgeschlagenen PG-/HTTP-Nachweise und erfolgreichen Wiederholungen bleiben
unter `docs/evidence/travel-v3-postgres-json-export-first-2026-11-03.txt` und
`docs/evidence/travel-json-export-http-{first,final}-2026-11-03.txt` getrennt.
Dies ist ein eigener Downloadfehler und keine nachgewiesene Erklärung des
älteren, nicht reproduzierten Katalogfehlers.

Der anschließende zusammenhängende Backendlauf bestand mit 104 Fällen in
12,034 Sekunden. Er umfasst alte und neue Rechenregeln, unabhängige Gegenfälle,
Originalauslagen, Zahlung/EÜR/Bank, gespeicherte Historie und echte HTTP-Aufrufe.
Überlappende Einzel- und Gesamtläufe werden nicht als zusätzliche unabhängige
Tests addiert. Maschinenlesbare Ergebnisse und geprüfte Dateihashes:
`CRM_ERP_REISE_V3_PRUEFUNG_2026-11-03.json`.

Vor dem Produktwechsel wurde derselbe Lauf einschließlich zweier
Reise-Lohnquellenfälle mit v3 als ausschließlich im Testprozess gewähltem
Standard ausgeführt: 106/106 Fälle bestanden in 12,137 Sekunden. Damit werden
die bisherigen gewöhnlichen Reisen sowie Quelle für steuerpflichtige
Erstattung und M auch unter v3 geprüft, während der Produktstandard noch v2
war. Nachweis: `docs/evidence/travel-v3-default-preview-2026-11-03.txt`.

Nach der tatsächlichen Umschaltung auf v3 bestand der unveränderte reguläre
Backendaufruf mit 107/107 Fällen in 14,768 Sekunden. Browser- und native
Clients bestanden ihre neuen und bisherigen Prüfungen: Node19/19, Flutter22/22
und Analyze2; anschließend liefen sowohl der neue tatsächliche Programmablauf
als auch der vollständige bisherige Reise-/Legacy-/EÜR-Ablauf unter aktivem v3
erfolgreich. Der neue Browserfall umfasst 2/3-Quote, getrennte Auslagen, fremde
Freigabe, tatsächliche dokumentierte Teilzahlung, Korrektur, unveränderte
JSON-Originalbytes/SHA256, Historie und eine Mobilansicht mit 390 Pixeln Breite.
Nachweise: `docs/evidence/travel-v3-active-final-2026-11-03.txt` und
[Clientabnahme](evidence/travel-v3-clients-2026-11-03.json).

Die Methode gilt für ein nachgewiesenes gemischtes Gesamtprogramm. Eine
separierbare private Urlaubsverlängerung ohne dieses Programm und mehrere
Reisen mit verschiedenen Quoten am selben Kalendertag benötigen eine eigene
belegte Abgrenzungsmethode. Sie bleiben ausdrücklich blockiert und werden durch
die erfolgreiche Abnahme der hier beschriebenen Methode nicht als gelöst
ausgegeben.
