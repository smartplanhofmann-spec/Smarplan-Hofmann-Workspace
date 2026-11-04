# Unabhängige Gegenprüfung der Ereignisintegration

Stand: 04.11.2026. Integrationsbaum `/workspace/smartplan-company-events-integration-20261104`, Hauptbasis `b0b96024f0a7cf2c7097fb3b77c64032265850a5`. Referenz ist der finale Owner-Handoff mit **116 Dateien**, Ursprungsbasis `4c2f0086b4a9979b7cbe9d261fc22a97cd046913`. Der Reviewer änderte keinen Produktcode. Eigene dauerhafte Testdatei, Gegenbelege und dieser Bericht sind separat abgegeben.

## Mergeprüfung

Alle 116 Owner-Dateien sind vorhanden. `prepared.json` und `resolved.json` enthalten dieselben 116 Pfade: neun Konflikte, fünf unveränderte Ersetzungen, 92 neue Dateien, zwei konfliktfreie Zusammenführungen und acht bereits identische Dateien. Die archivierten vorherigen Dateien stimmen mit ihren angegebenen Hashes überein. Vor den abschließenden Browserfixes entsprachen 105 Dateien exakt dem Ownerstand und 115 exakt dem aufgelösten Kandidaten; die einzige Abweichung zum Kandidaten war die ausdrücklich angekündigte zusätzliche V2-Preisprüfung in `company_event_sources.py`. Die späteren zwei Browserfixes sind als eigene geprüfte Änderungen im finalen Manifest erkennbar.

- `business_session.dart` enthält ausschließlich additive Änderungen gegenüber b0b9602. Der gesamte neue Ereignisblock entspricht exakt dem Ownerstand. Bestehende Source5-, historische Anlagen-, V2-Verbraucher-, Originalnonce-, In-flight-Future- und Identitätsregeln wurden nicht ersetzt. `api.dart` und `business_widgets.dart` sind bytegleich zur Hauptbasis.
- In `office.js` bleiben alle bisherigen Bedingungen zur Erhaltung unklarer Aufträge erhalten; entfernt man ausschließlich den neuen Ereignispfad aus der entsprechenden Bedingung, ergibt sich exakt die vorherige Zeile. Bestehende Source5-Dialogparameter, Anlagen-/Anfangsbestands-Bereinigung und V2-Quellenwiederholungen bleiben vorhanden. Der neue Validator erhält eine isolierte Kopie des tatsächlichen Originalbodys; die bereits vorhandene Prüfung auf dieselbe Sitzung und Pendingoperation erfolgt weiterhin nach dem asynchronen Validator.
- Die Weballowlist verliert keinen bisherigen Dateieintrag. API-/Schema-Registrierungen ergänzen nur das Ereignismodul beziehungsweise dessen geschützten Pfad. Die Funktionen und Klassen von `business_schema.py` sind per AST vollständig unverändert zur Hauptbasis; der Finanzhorizont **13** und der geforderte Restorebericht **14** bleiben bestehen. Die Registrierung ergänzt die getrennte Ereignisfamilie. Beide Restorewege ergänzen die Ereignissperre und erhalten die vorherigen Bereinigungen.
- Beide Paketlisten behalten alle ursprünglichen Backenddateien und ihre Reihenfolge: **131 → 134**. Alle ursprünglichen Operatorpfade bleiben ebenfalls in ihrer Reihenfolge erhalten: **138 → 150**. Windows-DLL-/Installerlisten bleiben unverändert. Auch aus den Pfadregistrierungen der CI verschwindet kein bestehender Eintrag.
- V2-Katalog-/Documents-/Pricing-Kern, Source5-Modul sowie Browserkatalog-, historische Anlagen- und Mehrfachbezugsseiten sind bytegleich zur Hauptbasis. Die bisherigen Assistentenfunktionen bleiben erhalten; die neue Firmenregelprüfung wird additiv aufgerufen.

Die Prüfdaten einschließlich aller 116 Hashvergleiche und Paketdifferenzen stehen in `initial-review.json`. Der endgültige Dateistand steht im separaten Manifest dieses Reviews.

## Zwei tatsächlich reproduzierte Browserbefunde

**1. Hintergrund vor dem ersten Dialog.** Ein echter lokaler Chromium-/MFA-/HTTP-Ablauf hielt die ursprüngliche Antwort von `/company-events/plans` zurück. Es bestand noch kein Dialog. Nach Aufruf des tatsächlichen DOM-`visibilitychange`-Handlers mit `document.hidden=true` öffnete die späte Antwort dennoch den privaten Dialog „Unternehmensereignisse“. Der rote Beleg zeigt `dialogs:1`. Dies war kein verlorener Konfliktzweig, sondern eine Lücke im übernommenen Browserstand.

Die Integrationsverantwortung korrigierte den bestehenden Visibilityhandler: Er invalidiert bei verborgenem Dokument den Ereigniskontext auch ohne vorhandenen Dialog. Die bisherige Bereinigung bereits sichtbarer privater Dialoge bleibt erhalten. Offene ursprüngliche Aufträge verbleiben unverändert in `OfficeApi`.

**2. Erfolg ohne Ausführungsergebnis.** Aus der tatsächlichen Fixture `external_unconfirmed.plan_after` wurde ausschließlich der abgeleitete Status auf `succeeded` geändert. Ausführungsnachweis und Originalhash blieben identisch; `outcome` blieb `null`. Der ursprüngliche Browserreader akzeptierte dies, und die tatsächliche UI-Funktion zeigte „Erfolgreich ausgeführt“. Der rote Beleg protokolliert `falseSuccessVisible:true` ohne Fehler.

Die Integrationsverantwortung übernahm die bereits im Native-Reader belegte enge Bedingung: `succeeded` benötigt eine Ausführung und ein tatsächliches `outcome.status=succeeded`. Gültige historische `stale`-/`suspended_after_restore`-Ansichten mit früherem Erfolg bleiben lesbar. Die tatsächliche angenommene ungeklärte Ausführung ohne Ergebnis bleibt ebenfalls gültig.

Beide ursprünglichen roten Gegenbelege sind erhalten. Die erste Browserausführung scheiterte vor Appzugriff an der eingeschränkten Prozessumgebung; die Wiederholung lief mit unverändert aktivierter Chromium-Namespace-/PID-/Netz-/Seccomp-Sandbox außerhalb dieser zusätzlichen Prozessbeschränkung. Keine Browser-Sicherheitsfunktion wurde abgeschaltet. Die Sichtbarkeitswechsel werden durch den tatsächlichen DOM-Handler mit kontrolliertem `document.hidden` ausgelöst; dies behauptet keinen unabhängigen Test eines Betriebssystemfensterwechsels.

## Unabhängige Nachprüfung

- **37/37** gezielte Ereignis-Nodefälle grün, darunter zwei neue dauerhafte Reader-/UI-Fälle in `web/office/tests/company-events-merge-review.test.mjs`.
- Echter lokaler Chromium-/MFA-/HTTP-Gegenlauf: vier Kombinationen aus Hintergrund beziehungsweise Rückkehr in den Vordergrund und verspätetem Erfolg beziehungsweise Fehler. In allen Fällen **0 private Dialoge und 0 private Fehlermeldungen**. Die Antwort wird erst nach dem tatsächlichen Sichtbarkeitshandler freigegeben.
- Die zwei neuen echten V2-Integrationsfälle des Roots separat erneut grün: Ein unveränderter unverwalteter Artikel erzeugt genau einen Entwurf mit `246,90` Netto; ein datiert verwalteter Artikel ohne ausdrückliche Preiswahl bleibt schon in der Vorbereitung gesperrt und erzeugt weder Nullpreisangebot noch Ausführung oder Versand. Der Root verwendet dafür die kanonische `Documents._positions(..., persist=False)`-Prüfung.

Die umfassenden Backend-, Flutter-, Paket- und PostgreSQL-Läufe werden unabhängig davon vom Root geführt. Dieser Review behauptet weder einen eigenen vollständigen Plattformlauf noch produktiven Versand oder eine Gesamtfreigabe der Software. Nach den gezielten Korrekturen verbleibt in diesem Prüfauftrag kein bestätigter offener Befund.
