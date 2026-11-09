# Korrektur zweier gebundener HTTP-Testaufbauten

Basis: `d4df2f562200fd5f527309c983bb3c9593ab2563`, geprüft am 09.11.2026.
Keine Produktionsdatei und kein Instanzschutz wurde geändert.

Die gemeinsame Import-HTTP-Fixture erzeugt inzwischen eine ausdrücklich
gebundene Datenbank. Zwei Verbraucher verwendeten noch den früheren Aufbau:

- `business_service_equipment_http_review_test.dart` tauschte die Datenbank
  gegen `ResourceCustodyTests.office`, verwendete jedoch Schlüssel, Ablage und
  Instanz der vorherigen Datenbank. Jetzt erhält die Ersatzdatenbank ein
  zusammenpassendes eigenes Tupel aus Schlüssel, Instanz und Ablage. Der
  temporäre Wurzelpfad wird vor der untergeordneten Fixture kanonisiert; der
  frühere Speicher bleibt unberührt.
- `business_company_events_http_test.dart` wollte die bereits gebundene
  Ausgangsdatenbank erneut mit anderen Instanzwerten binden. Es übernimmt nun
  deren bestehende gültige Bindung. Ein nicht mehr passender historischer
  `create_app`-Textersatz entfällt.

Beide Tests unterstützen `SMARTPLAN_TEST_BACKEND` und lesen über echtes HTTP
den bestätigten Offline-Kontext einschließlich Instanz und aktuellem Benutzer.
Die bisherigen Nachweise für unveränderte Wiederholung, geschlossene Ansichten,
Aufgabenanlage und Originalhistorien bleiben erhalten.

Alle 20 direkt importierenden Testdateien sowie die gemeinsame Basisfixture
wurden auf Datenbankaustausch, neue Bindungen und ersetzte Schlüssel/Ablagen
geprüft. Nur diese beiden Fälle waren betroffen. Die anderen Verbraucher und
der gemeinsam verwendete Rechnungs-Seed behalten ihre Ausgangsdatenbank.
Dies ist eine Quellprüfung, keine Behauptung eines erneuten vollständigen
App-Testlaufs.

Tatsächliche Prüfungen:

- Beide unveränderten Ausgangs-Seeds beendeten sich vor der Serverankündigung
  mit `InstanceConfigurationError`; die früheren Fehler bleiben erhalten.
- Beide korrigierten Seeds starten auch mit einem echten Symlink als übergebenem
  Tempwurzelpfad. Ein anschließender HTTP-Abruf bestätigt `bound_v2` und den
  passenden Benutzer. Das prüft die portable Behandlung des macOS-Tempalias.
- Die beiden betroffenen Flutter-Dateien bestehen gemeinsam: **3 bestanden,
  0 Fehler, 0 ausgelassen**. Die Meldung zur fehlenden Visual-Studio-Installation
  steht im Linux-Protokoll, hat diesen Lauf aber nicht verhindert.
- Formatierung und `git diff --check` ohne Befund.

[Prüfmanifest und exakte Befehle](evidence/fixture-binding-followup-2026-11-09/verification.json),
[vorherige Startfehler](evidence/fixture-binding-followup-2026-11-09/before-startup.json),
[Symlink-/HTTP-Nachweis](evidence/fixture-binding-followup-2026-11-09/symlink-startup.json),
[Verbraucherprüfung](evidence/fixture-binding-followup-2026-11-09/consumer-review.json).

Die parallel laufende vollständige App-Prüfung auf dem unveränderten
Ausgangsstand ist ein eigener Nachweis. Sie wurde durch diese isolierte
Korrektur nicht verändert oder als bestanden umgedeutet.
