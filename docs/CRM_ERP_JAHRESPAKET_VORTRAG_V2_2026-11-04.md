# Versionierter Nachtrag: Jahresvortrag im Jahresnachweis

Dieser getrennte Arbeitsbaum ergänzt den ursprünglichen Backendkandidaten
`e2f228173bb6d0eb3408d1cf48dadf0f7cbfd0e138c19ea3dc8ed8f89f13d069` um den
tatsächlichen Jahresvortrag aus Backendmanifest
`6c665abc663964c27dff1a38baf61a895d064904a7aa3957079e14e84db8221a`.
Die gemeinsame Basis und 14 gezielte Backendübernahmen sind in
`work/verification/year-package-carryover-baseline.json` gebunden. Drei additive
Transportkonflikte erhielten sowohl die vorhandenen datierten Katalogrouten
als auch die neuen Jahresvortragsrouten. Unfertige Clients wurden nicht kopiert.
Vor Implementierung bestanden 27 tatsächliche Jahresvortrag-/V1-Domainfälle.

`accounting_year_package_v2.py` und der eigenständige Standardbibliotheksprüfer
`accounting_year_verify_v2.py` ergänzen ausschließlich die konkrete Quellart
`opening_year_values`. Der alte V1-Builder bleibt unverändert. Der unabhängige
V1-Prüfernachtrag gegen drei tatsächlich entfernbare Vorläufer ist ausdrücklich
ein gemeinsamer Korrekturkandidat vor Freigabe; seine finalen Hashes werden im
Nachweis getrennt gebunden. Die ursprünglichen EÜR-Exportartefakte werden durch
keinen dieser lesenden Wege umgeschrieben.

Die Ausgabeversion wird ausschließlich anhand des gespeicherten Exportberichts
und seines damaligen ausgewählten EÜR-Präfixes bestimmt. Nur eine enthaltene
Jahresvortragsquelle oder ein damaliger ungelöster Jahresvortragsverweis benötigt
`smartplan-year-evidence-v2`. Später hochgeladene Journale, neue Fassungen oder
heutige Katalogquellen ändern die Versionswahl eines alten Exports nicht.
Unbekannte Quellen bleiben ausdrücklich gesperrt.

Die bisherigen GET-Routen bleiben bestehen. Die 16 Metadatenfelder behalten ihre
Form; einzig `format` kann für betroffene Exporte zusätzlich den tatsächlichen
Wert `smartplan-year-evidence-v2` besitzen. Die Metadaten-DTO-Version bleibt 1.
Feature `accounting_year_evidence_v2` kennzeichnet diesen zusätzlichen Leser.
Die ursprüngliche Exportkennung, der EÜR-Eintragshash, Jahr und Vollständigkeit
bleiben unverändert. Beide Versionen benötigen aktuelle Einzelquellenrechte;
vor der Clientablage bleibt der zweite identische Metadatenabruf erforderlich.

Die neue Quelle bindet genau ihre damalige Jahresrevision, alle früheren
Revisionen desselben Jahres, die unveränderten Annahmebefehle und Quittungen,
das eigenständige Zeitraumjournal sowie die ursprünglichen Rechnungs-,
Zahlungs- und bereits ausgeübten Vorsteuerbelege. Kanonische Altposten werden
an ihre ursprünglichen IDs und Inhaltshashes gebunden; spätere neue Zahlungen
werden nicht rückwirkend hineingenommen. Vollständig erledigte Altbelege behalten
ihre tatsächlichen Originale und ursprünglichen Journalkennungen.

Der Prüfer bindet die neue Reportprojektion an den zum Exportzeitpunkt aktiven
EÜR-Eintrag, kontrolliert Quelle, Originaljournal, Quittung und Vorläufer und
verlangt die notwendigen Originaldateien aus den intrinsischen Quellenfeldern.
Er berechnet keine Steuergesetze neu und bestätigt weder eine behördliche
Einreichung noch DATEV-Kompatibilität. Historische Deckung macht einen noch
offenen Jahresbericht nicht vollständig. Insbesondere entstehen durch den
Nachweis keine Geldbewegung und kein neuer Vorsteueranspruch.

Der Adapter führt keine Tabelle, Mutation, Migration oder neue Finanzhorizont-
Nummer ein. Finanzhorizont 15 und Restorebericht 16 gehören ausschließlich zum
separat entwickelten Jahresvortrag. Die ursprünglichen Ausgabegrenzen und der
geschlossene ZIP-Pfadvertrag gelten unverändert. PostgreSQL erhält getrennte
frische Snapshots für Versionswahl und Ausgabe; der unveränderliche Exporteintrag
kann zwischen diesen Leseschritten nicht seine Version wechseln.

Erster tatsächlicher Adapterlauf: sieben Fälle bestanden (5,851 Sekunden),
nach Übernahme des V1-Prüfergegenfalls erneut sieben (6,461 Sekunden). Enthalten
sind 119,00 Jahresausgabe bei nur 59,50 neuem Cash, altes VAT-Datum, Teildeckung,
geschlossene Altbelege, Quittungs-/Originalmanipulation, echte Revisionen bis zur
Aufhebung/Korrektur, unabhängiger Prüfer und bytegleiche spätere V1-Wiederholung.
HTTP, endgültige tatsächliche V2-Fixture, Paketregistrierungen und unabhängiger
Review bleiben vor einer finalen Übergabe gesondert abzunehmen.

## Nachtrag des finalen Prüfvertrags

Wie V1 verlangt V2 zwingend den separat authentisiert bestätigten ZIP-Hash.
Manifest und Prüferergebnis weisen `intrinsic_dependency_closure=false` aus.
Die alten Journale binden keinen vollständigen Abhängigkeitsindex; der neue
Adapter behauptet dafür keine rückwirkende Vollständigkeit. Fehlender/falscher
Außenanker wird abgewiesen. Die direkten inneren Original-/Quittungs-/
Vortragsprüfungen bleiben zusätzlich aktiv. Die echten V1-Exportoriginale
bleiben unangetastet.

Nach diesem Nachtrag bestehen acht Fälle inklusive echtem lokalem HTTP in
11,980 Sekunden. Die tatsächliche separate V2-Fixture umfasst vier Szenarien,
472173 Bytes, SHA-256
`2f9a1664eb1bf1d2615c7f25de9673aba4dc8ee95acad32367588411ba9f64d5`.
Sie liegt bytegleich unter `docs/fixtures/accounting_year_package_v2.json` und
`app/test/fixtures/accounting_year_package_v2.json`. Die sechs V1-Szenarien werden
nicht dadurch ersetzt. Ein echter befüllter PG-Restorefall ist vorbereitet und
wartet auf den reservierten Testslot. Clienterweiterungen folgen getrennt nach
der V1-Abnahme; dieser Backendnachtrag behauptet keine fertigen V2-Oberflächen.
