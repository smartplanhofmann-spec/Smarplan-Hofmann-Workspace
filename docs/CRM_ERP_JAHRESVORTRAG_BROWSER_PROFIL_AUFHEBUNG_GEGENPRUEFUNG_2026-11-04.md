# Unabhängiger Browsernachtrag: historische Aufhebung ohne heutigen Buchführungsbeginn

Stand 2026-11-04, Baum `/workspace/smartplan-opening-year-values-20261104`. Separater Nachtrag zum eingefrorenen Browserreview; die bisherigen Owner- und Reviewmanifeste mit SHA-256 `7307bc17673de238bb8403b0772cfdd01ded47494843312eafea18edf96fe520` und `d4a11801dd4d44bd615ae466dd152994f39a19d68f03ea7e7d097dc9fc637c62` bleiben unverändert.

## Tatsächlicher Befund

Die reale separate Backendfixture `docs/fixtures/accounting_year_values_native_independent_v1.json`, Szenario `void_after_missing_start`, belegt zunächst eine angenommene Jahresquelle und ihre tatsächliche EÜR-Übernahme. Solange diese Übernahme aktiv ist, scheitert die Quellenaufhebung mit 409. Danach erfolgt eine tatsächliche EÜR-Gegenbuchung. Das heutige Profil wird ohne Buchführungsbeginn bestätigt; der aktuelle Quellenzustand hat nun `profile:null` und `can_prepare:false`. Die Backendvorschau und anschließende tatsächliche Annahme der unveränderten historischen Aufhebung bleiben rechtmäßig im implementierten Vertrag möglich: alter Inhalt und alte `profile_ref` bleiben erhalten, ausschließlich `status` wird `void`.

Der unveränderte Browserstand bot diese Aufhebung nicht an, weil die Schaltfläche gemeinsam mit neuen aktiven Vorträgen hinter der heutigen vollständigen Profilfreigabe lag. Der erste eigene Lauf hatte **4 Fälle, davon 3 bestanden und 1 fehlgeschlagen**: „Fälschlichen Jahresvortrag aufheben“ fehlte in der bestehenden Detailansicht. Echte Eingaben, Originale, vorheriger 409, EÜR-Gegenbuchung und gültige ursprüngliche Quittung wurden im positiven Kontrollfall gelesen. Die heutigen Schreibrechte- und Modulsperren waren bereits korrekt.

Roter Lauf, damalige vier Tests, unveränderte Produktkopien, echte Fixture und Quellhashes stehen in `docs/evidence/year-values-browser-profile-void-independent-2026-11-04/before-fix/`. Der Reviewer änderte keinen Produktcode und keine Backenddateien; der Generator wurde für diesen Nachtrag nicht erneut ausgeführt.

## Enger Ownerfix und Nachprüfung

Der Browserowner trennt die historische Aufhebung von einer neuen aktiven Quellenannahme. Die Ausnahme verlangt eine aktuell noch aktive, exakt passende Originalreferenz sowie frische globale Schreibrechte und ein aktives Finanzmodul. Der Auftrag übernimmt ausschließlich das unveränderte ursprüngliche Payload und dessen damalige Profilreferenz. Eine zwischenzeitlich ersetzte oder bereits aufgehobene Originalfassung wird verworfen. Die allgemeine `yvInput`-Freigabe für neue aktive Werte bleibt unverändert an das aktuelle Profil gebunden. Der Owner ergänzt außerdem einen Kontextcheck nach der asynchronen Originalprüfung vor dem Vorschauauftrag.

**7 eigene Nachtragsfälle bestanden**:

1. Tatsächliche Blockierung vor EÜR-Gegenbuchung, danach gültige Backend-Aufhebung trotz fehlenden aktuellen Beginns.
2. Vollständiger ausdrücklicher Browserablauf von Detail über Vorschau/Annahme zur Historie; gesendeter Body bis auf seine neu erzeugte Requestkennung exakt gleich der tatsächlichen Fixture.
3. Keine Aufhebung bei fehlendem aktuellem Schreibrecht.
4. Keine Aufhebung bei abgeschaltetem Finanzmodul.
5. Verlorene Annahmeantwort nach heutiger Profiländerung: identischer ursprünglicher Body und identische Nonce im Replay.
6. Nach geöffnetem Aufhebungsdialog entzogene Schreibrechte verhindern bereits den Vorschau-POST.
7. Tatsächlich inzwischen aufgehobene Originalfassung verhindert einen veralteten zweiten Aufhebungsauftrag.

Der abschließende gemeinsame **eigene 37er-Lauf** umfasst diese sieben sowie die unveränderten bisherigen 30 Fälle: 37 bestanden, keine Fehlschläge, Abbrüche oder Skips. Produkt- und Testhashes waren vor und nach diesem Lauf identisch. Kein separater unabhängiger Chromium- oder PostgreSQL-Lauf wird behauptet; die kontrollierten Node-Abläufe verwenden den tatsächlichen `OfficeApi` und echte Backendantworten. Die bisherigen Original-/Kontextgegenfälle bleiben eigenständig archiviert und unverändert.

Testdatei: `web/office/tests/accounting-year-values-profile-void-independent.test.mjs`. Maschinenlesbarer Nachweis: `docs/evidence/year-values-browser-profile-void-independent-2026-11-04/manifest.json`. Die Rootintegration benötigt die beiden aktuellen privaten Jahreswerte-JS-Module zusätzlich zur unveränderten bisherigen Ownerfusion. Dies ist eine begrenzte Produktgegenprüfung und keine Vollständigkeits- oder steuerliche Zulassungsbehauptung.
