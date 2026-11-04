# Unternehmensereignisse: gezielte Übergabe zur Integration

Arbeitsbaum `/workspace/smartplan-company-events-20261104`; exakte Basis
`4c2f0086b4a9979b7cbe9d261fc22a97cd046913`. Es gab keine später kopierte
Runtime-Basisüberlagerung. `work/verification/company-events-native-baseline.json`
protokolliert den Ausgangsstand der gemeinsamen Native-Dateien und die damalige
erste echte Fixture; die abschließende Fixture hat SHA256
`2b10534178c4efef9c6ea6ed69b626b675617b3da6e6d2168915d5394bc29f20`.

Backend, Browser und Native sind geprüft und stabil. Die Native-Ownerabnahme
umfasst 149 Tests und eine Analyse ohne Befunde. Im anschließenden unabhängigen
Review wurde die falsche Kombination `status=succeeded` mit `outcome=null`
reproduziert. Der gezielte achtzeilige Readerfix ist durch 74 gemeinsame Fälle
(14 unabhängige und 60 Ownerfälle einschließlich echtem HTTP) erneut geprüft.
Die historischen Rotbelege bleiben erhalten. Nachweis:
`docs/evidence/company-events-native-independent-2026-11-04/manifest.json`
mit benachbarter README und eigener Testdatei. Das neue Ownerhandoff hat SHA256
`fa00c556a991bee7395ff458ce49a1af9e56a5f48fda4bd636dd4c4d54e3459c`.

Der Root-Integrationsstand ist inzwischen
`b0b96024f0a7cf2c7097fb3b77c64032265850a5`; er enthält den separaten
Kostenfix bereits sowie Source5-, Anlagen- und Katalog-V2-Erweiterungen.

## Quellen und belegte Prüfungen

- Backend-/APIvertrag und Fortschritt:
  `CRM_ERP_UNTERNEHMENSEREIGNISSE_API_2026.md`,
  `CRM_ERP_UNTERNEHMENSEREIGNISSE_VERTRAG_2026-11-04.md`,
  `CRM_ERP_UNTERNEHMENSEREIGNISSE_FORTSCHRITT_2026-11-04.md`.
- Eigene Backendevidenz `docs/evidence/company-events-2026-11-04/manifest.json`:
  40 neue und unabhängige Domain-/HTTP-Fälle, 75 gemeinsamer Legacy-/Gatelauf,
  drei echte PostgreSQLfälle mit Parallelität/Runtime-ACL/befülltem Restore,
  19 zusätzliche CLI-/Worker-/Instanzfälle. Die Mengen überschneiden sich.
- Browservertrag und Endnachweis:
  `CRM_ERP_UNTERNEHMENSEREIGNISSE_BROWSER_2026-11-04.md`,
  `docs/evidence/company-events-browser-2026-11-04.json`;
  557 Node-Fälle, tatsächlich gerenderter Ereignisflow und alter Assistantflow.
- Nativevertrag und Ownernachweis:
  `CRM_ERP_UNTERNEHMENSEREIGNISSE_NATIVE_2026-11-04.md`,
  `docs/evidence/company-events-native-2026-11-04/handoff.json`;
  60 neue + 89 bestehende Tests, davon echter HTTP-Widgetablauf, Analyzer ohne Befunde.
- Echte gemeinsame Clientfixture in `docs/fixtures/company_events_2026.json`
  und `app/test/fixtures/company_events_2026.json`, reproduzierbar mit
  `scripts/generate-company-events-fixture.py`. Keine geratene DTO-Ergänzung.

Die Dateiliste mit SHA256 und Basishashes wird unter
`work/verification/company-events-handoff-files.json` erstellt. Neue Dateien
können nach Hashprüfung übernommen werden. Bereits vorhandene globale Dateien
brauchen einen gezielten Merge; die Quelle enthält ältere Source4-/Opening-
Registrierungen und darf den neueren Source5-/Assets-/Katalog-V2-Stand nicht ersetzen.

## Globale Änderungen, die erhalten werden müssen

| Stelle | Exakte additive Änderung |
|---|---|
| `business_schema.py` / `business_api.py` | Modul `business_company_events`, Feature aus seinem Vertrag, strikte company-events-Routen. Kein Finanzhorizont wird heruntergesetzt oder durch diese Erweiterung erhöht. |
| `business_assistant.py` | Bestehende eventbasierte Ausführung berücksichtigt Unternehmensregeln; beide nativen Beleg-/Mahngates erkennen den exakten Unternehmensclaim und prüfen dessen gebundene effektive Regeln. |
| `business_assistant_sources.py` und enger weiterer Assistant-Hunk | Separater Kostenfixv2, siehe unten. |
| `restore.py` / `online/restore.py` | Neue offene Ereignispläne appendiert sperren; alte Claims und Ergebnisse bleiben erhalten. Bestehende Restoreprüfungen und höhere Finanzhorizonte unverändert weiterführen. |
| `company_export_catalog.py` | Exakte zehn neue Tabellen, technische Requests weiterhin nicht im fachlichen Export; Präfix sensibel und quellenabhängig, keine pauschale Personalaufbewahrung. |
| `online/web.py` | Zwei zusätzliche statische Browsermodule. |
| `scripts/native-release.py`, `scripts/package-windows-support.py`, CI | Drei neue Backenddateien, Worker/Verträge/Nachweise; HTTP/PG-Testdiscovery und echter Browserworkflow. Flutter-Discovery umfasst alle neuen Tests. |
| `web/office/office.js`, CSS, E2E/Fixturehost | Enger UI-Einstieg, Lifecycle, Originalbody an awaitReceipt sowie neuer tatsächlicher Testworkflow. Neuere Source5-/Assets-/V2-Hooks gezielt erhalten. |
| `app/lib/business_session.dart`, `business_assistant.dart` | Ereignis-Retry mit Originalbody/Originalreceipt und aktuellen Rechten; enger Einstieg und Inflight-Regeln. Neuere Source5-/Assets-/V2-Sessionzweige erhalten. `api.dart` und `business_widgets.dart` wurden nicht geändert. |

Der letzte CLI-Nachtrag verwendet den bereits vorhandenen
`online.instance.verify_worker` vor dem Scan. `SMARTPLAN_INSTANCE_ID` und
`SMARTPLAN_PUBLIC_HOST` müssen zur gebundenen Datenbank passen. PostgreSQL wurde
abschließend freigegeben; kein Restoreziel und keine offene Testverbindung blieb.

## Separat integrierbarer Kostenfix

`docs/evidence/assistant-cost-total-v2-2026-11-04/runtime.patch` umfasst genau
die beiden Kostenhunks, keine Unternehmensereignisgates. Root hat diesen
Nachtrag bereits separat erhalten. Falls er im Zielstand schon enthalten ist,
nicht erneut oder über ein altes vollständiges Assistant-Modul übernehmen.
Neue tatsächliche Kosten verwenden `costs.total_net` genau einmal und die
ausdrückliche Basisversion; alte unmarkierte Originalkontexte/Quittungen bleiben
bytegleich und offene alte Pläne werden durch den neuen Quellenhash veraltet.

## Gemeinsamer Katalog-V2-Gegenfall

Die Ereignisvorlage `offer.draft` bindet derzeit Artikel-ID, Revision und Menge,
aber keine ausdrückliche datierte Preiswahl. Ein verwalteter V2-Artikel darf
deshalb keinen technischen Masterpreis 0 als Kundenangebot verwenden. Der
gemeinsame Integrationsfall muss den vorhandenen Document-Fachvertrag tatsächlich
aufrufen und eine fehlende datierte Auswahl klar sperren. Weder ein geratenes
Vorlagendatum noch ein Ersatzpreis wird durch dieses Paket eingeführt.

Eine Hersteller- oder Steuerübertragung, echte Nachricht oder produktive
Automatik wurde nicht ausgelöst. Der gemeinsame neue
Hauptstand und dessen Integrationsabnahmen bleiben eigene Nachweise.
