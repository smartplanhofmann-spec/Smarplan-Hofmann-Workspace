# Unabhängige Prüfung: individueller Minijob v11

Stand: 2026-11-09. Geprüft wird ausschließlich der additive Vertrag
`de_2026_individual_minijob_month_v11`, Quellvertrag 3. Dies ist kein Nachweis
für eine vollständige Lohnabrechnung oder eine Freigabe der gesamten Software.

## Prüfstand

- Eigene Arbeitskopie `smartplan-minijob-v11-pg-review-20261109` auf dem
  integrierten Backend `7b0b84cdc74d51199108a39b0b79f0529ae18691`.
- Nach bestätigtem Befund zusätzlich Autorfix `57423ba`, lokal unverändert
  übernommen als `c5cb37092ba95d65c42cce7eaa1c611b0aeb1381`.
- Ausschließlich synthetische lokale Daten. Eigener PostgreSQL-16.15-Container
  `smartplan-minijob-v11-review-pg-20261109` auf `127.0.0.1:32782`, eigene
  Datenbanken und Runtime-Rolle. Kein Zugriff auf einen Kundenserver.
- `pg_dump`/`pg_restore` liefen über ausschließlich an diesen Container und
  die beiden erlaubten Prüfdatenbanken gebundene lokale Wrapper.

Nach dem erfolgreichen Abschluss wurde ausschließlich dieser Prüfcontainer
entfernt; die anschließende Namensabfrage zeigte keinen verbleibenden Container.

## Befund und Korrektur

Vor der Korrektur konnte ein absichtlich beschädigter, aber korrekt gehashter
Altdatensatz die Prüfung auf Nichtverwendung passieren. Ein gültiger
Hüllhash allein belegte keinen fachlich lesbaren Originaldatensatz. Der
Gegenbeweis scheiterte deshalb vor dem Fix wie erwartet mit „Problem not raised“.
Dies war ein kontrollierter Integritätsfehler in einer Wegwerfkopie, kein
über die reguläre API erzeugter gültiger Abrechnungslauf.

Der Autorfix prüft nun die vollständigen historischen Quellen, Berechnungen
und Quittungen aller fünf abhängigen Fachmodule vor der Referenzsuche. Die
unabhängige Nachprüfung verlangt HTTP 409 beziehungsweise `Problem(409)`,
unveränderte Altzeilen, keine zusätzliche Fallrevision und keine neue Quittung.
Auch eine tatsächlich früher verwendete v5-Revision bleibt gesperrt, wenn die
neueste Revision inzwischen ein ansonsten zulässiger, nicht berechenbarer
individueller Minijobfall ist. Alte erfolgreiche Aufträge bleiben unverändert
wiederholbar.

## Ausgeführte Nachweise

| Prüfung | Ergebnis |
| --- | --- |
| Vier vorhandene PostgreSQL-/MFA-/Restore-/Konkurrenzfälle vor dem Fix | 4/4, 90,473 s |
| Zusätzlicher echter PostgreSQL-Upgrade-/GKV-/Originalquittungsfall vor dem Fix | 1/1, 28,507 s |
| Drei unabhängige fachliche Gegenproben nach dem Fix | 3/3, 5,974 s |
| Tatsächlich unter CRLF erzeugte v4-/v5-/v11-Originale unter LF wieder öffnen | 1/1, 6,740 s |
| Abschließender PostgreSQL-Lauf nach dem Fix | 6/6, 207,390 s |
| Historische Kernmodule gegen vorhandenes Hashmanifest | 32/32 bytegleich |
| Unverändertes Gesamtziel | 23.863 Bytes, SHA-256 `a4dea28f6de4afd3e36d1549441aad91ce16dad374f56097979cc2d79b07fbf5` |

Der abschließende Datenbanklauf umfasst echte MFA-/HTTP-Aufrufe, frischen
Rechteentzug vor einer idempotenten Wiederholung, Original-PDFs nach Neustart,
Geldfluss/EÜR mit Dump und Wiederherstellung, zwei konkurrierende Korrekturen,
zwei konkurrierende Laufannahmen sowie die beiden unabhängigen Upgrade- und
Integritätsgegenproben. Die beschädigte Historie wird nach dem Negativtest
nicht als gültiger Sicherungsbestand behandelt.

Die GKV-Quelle bleibt `statutory_other` mit der belegten Einordnung
`statutory_family`. Das technische PAP-Feld `PKV=1` ersetzt diese Originalquelle
nicht. Bei 500 EUR und Steuerklasse V werden 18 EUR tatsächlicher Arbeitnehmer-RV
und 48,66 EUR individuelle Lohnsteuer geprüft; der Nachweis erfindet keine
zusätzliche Zahlung. Der Vertrag erlaubt weder einen anderen Regelwechsel noch
eine automatische Migration benutzter Originale.

Der Plattformtest führt die tatsächlich nach CRLF umgeschriebenen Python-Dateien
in einem eigenen Prozess aus. Er erzeugt eine echte SQLite-Datenbank mit
v4-Periodenfall, v5-Original, v11-Korrektur, Quittungen, Lauf und PDF. Unter den
unveränderten LF-Modulen werden Plan, Quellen, alte und neue Quittung sowie
PDF-Bytes überprüft. Es werden keine Herkunftshashes nachträglich ersetzt.

## Erhaltene Fehlversuche und Grenzen

Die erste zusätzliche Altidentitäts-Fixture versuchte irrtümlich einen zweiten
Identitätsdatensatz für denselben Profilstand neu anzulegen. Die API wies das
korrekt mit 409 ab. Der Testaufbau verwendet nun ausdrückliche begründete
Korrekturversionen; deren alte Quellen bleiben in der historischen Fassung.
Das erste Fehlerprotokoll bleibt als Aufbaufehler erhalten und wird nicht zu
einem Produktfehler oder einem erfolgreichen Lauf umgedeutet.

Rohprotokolle und SHA-256-Manifest liegen unter
`docs/evidence/minijob-v11-independent-review-2026-11-09/`.
Die ergänzende Codeprüfung fand nach dem Fix keine weitere bestätigte Lücke
und keine Rekursion zurück in den ausschließlich beim Anlegen aufgerufenen
Migrationsschutz. Aussagen zu Windows-/iPhone-Paketbau oder Liveinstallation
werden aus diesen Backendprüfungen nicht abgeleitet.
