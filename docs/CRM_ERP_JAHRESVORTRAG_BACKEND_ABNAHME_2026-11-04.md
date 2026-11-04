# Jahresvortrag – eingefrorener Backendstand

Der Backendumfang im isolierten Baum
`/workspace/smartplan-opening-year-values-20261104` ist implementiert und über
wirkliche Quellen, lokale/MFA-HTTP-Anfragen und PostgreSQL geprüft. Keine
Browser-/Nativeoberfläche oder unabhängige Gesamtfreigabe wird damit behauptet.
Hauptprojekt und laufende Altpostenclients wurden nicht beschrieben.

Grundlage: Hauptcommit80e051a plus exakt eingefrorenes Altpostenbackend, gebunden
in `work/verification/opening-items-backend-baseline.json` (1959 Dateien).
Nur die Änderungen gegenüber dieser Grundlage gehören zu diesem Paket.

## Ergebnis

Belegte alte laufende Jahreswerte erhalten ihre ursprünglichen Zahlungs- und
Steuerperioden. Ein eigener Zeitraumjournalbeleg, eindeutige Originalidentitäten,
ursprüngliche Buchungsidentitäten und exakte Kontrollsummen binden die Übernahme.
Ein durchgeführter Fall mit59,50 EUR Zahlung vor Beginn und59,50 EUR danach
liefert119 EUR Jahresaufwand, bei nur59,50 EUR neuer Geldbewegung und unverändertem
Anfangssaldo1000 EUR. Historische Juni-Vorsteuer19 EUR bleibt historisch; neue
November-Vorsteuer0 EUR. Aktueller berechneter Kontostand940,50 EUR.

Vollständig erledigte externe Belege benötigen keinen künstlichen offenen Posten.
Unbelegte Nullwerte, fehlende bekannte Altwerte, neue Scans derselben wirtschaftlichen
Rechnung, geänderte Quellen/Profile und geschlossene Perioden dürfen den Vertrag
nicht umgehen. Ein unabhängiger ausdrücklich belegter Nulljournalzeitraum ist
hingegen tatsächlich testbar. Unvollständige Vorjahresanfangsdeckung bleibt im
Jahresbericht offen. Alte Exporte und Quittungen bleiben unverändert.

Der enge Umfang umfasst gewöhnliche vollständig betriebliche inländische19-/7-Prozent-
Fälle bei fortgeführter EÜR/Regel-/Istbesteuerung. Anlagen, Lohn, frühere Finanzamts-
zahlungen, Sondersteuerfälle und Methodenwechsel benötigen weitere eigene belegte
Quellenverträge. Bekannte alte AfA verhindert eine unzutreffende Deckungsfreigabe.

## Durchgeführte Prüfungen

| Prüfung | Ergebnis und tatsächliche Grenze |
| --- | --- |
| Neue Regeln/Domain/Registrierung/Local- und MFA-HTTP |25/25 grün,16,673s |
| Zusätzlich unabhängiges Nulljournal und späte atomare Auditunterbrechung |2/2 grün,1,424s |
| Tatsächliche PostgreSQL-Verbindungen/Runtime-ACL/Neustart/belegter Dump-Restore |3/3 grün,17,276s |
| Bestehende EÜR/Bank/Anfangssalden/Anlagen/Altposten |117/118 zunächst grün; einziger Fehler veraltete volle Horizont-Erwartung14 statt15 |
| Enge Korrektur dieses Tests plus ursprüngliche historische Scopeverträge |15/15 grün,5,916s; historische Originalversionen bleiben unverändert |
| Weitere aktuelle/historische Finanz- und echte HTTP-Verträge |173/181 zunächst grün;8 veraltete explizite aktuelle Horizont-/Feldmengen |
| Gezielter Nachlauf dieser8 Tests nach ausschließlich Testscopekorrektur |8/8 grün,6,687s; Runtime unverändert |

Die anfänglichen roten Logs werden erhalten. Der erste neue Domainlauf enthielt
einen Fehler im Testaufruf einer nicht vorhandenen öffentlichen Monatsoption;
die tatsächliche vorhandene Monatsprojektion wird nun verwendet. Die erste
Registrierungsprüfung fand den fehlenden strikten Routenpräfix; dieser wurde vor
allen finalen HTTP-/PG-Prüfungen ergänzt. Kein alter fachlicher Prüffall wurde
entfernt oder inhaltlich abgeschwächt.

Der tatsächliche PG-Restore bindet Finanzhorizont15/Restorebericht16, Originalbytes,
Annahmequittungen, alte und neue Jahresexporte und die echte spätere59,50-EUR-Zahlung.
Runtime darf weder Freigaben erteilen noch Originaltabellen ändern/löschen/leeren.
Zwei parallele Verbindungen beweisen exakte Wiederholung beziehungsweise
`201/409 not_accepted` bei konkurrierenden neuen Fassungen. Nach Abschluss wurde
rein lesend über den Containeroperator geprüft: einziges Testziel
`smartplan_check`, keine Restoreziele, keine anderen Clientverbindungen. Slot
PG55433 wurde ausdrücklich freigegeben.

## Handoff

- API-/Clientvertrag: `docs/CRM_ERP_JAHRESVORTRAG_API.md`.
- Tatsächliche3-Szenarien-Fixture: `docs/fixtures/accounting_year_values_v1.json`,
  654241 Bytes, SHA-256
  `441f0665a27dd304f229dbf604c09f5463013c636c222c47cf8f581e3b7eb5d5`.
- Runtimeprüfung: `work/verification/year-values-runtime-review-snapshot.json`;
  alle17 Runtime-/Paketdateien seit erfolgreichem PG-Lauf unverändert.
- Backendmanifest und additiver Patch:
  `docs/evidence/year-values-backend-2026-11-04/manifest.json` und `backend.patch`.

Offen sind die unabhängige Produktgegenprüfung, anschließende Integration beider
Clients und der separate versionierte Anschluss an das Jahresbelegpaket. Keine
Steuermeldung, kein echter Zahlungsauftrag und kein Produktionsbestand wurde
verändert. Keine eigene Git-Staging-/Commitaktion wurde ausgeführt.
