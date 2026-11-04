# Unternehmensereignis-Browser: Abschlussnachweis

Der Browserumfang ist im isolierten Arbeitsbaum implementiert und geprüft. Dies ist keine Fertigmeldung des Gesamtziels und keine Produktionsauslieferung.

- Vollständige Node-Regression: 557/557 tatsächliche benannte Tests, keine ausgelassen. Darin 35 gezielte Companyfälle, davon 13 unabhängig.
- Unabhängige Backendgegenfälle gegen den endgültigen Kern: 16/16.
- Tatsächlicher neuer Chromium-/MFA-/HTTP-Ablauf sowie bestehender Assistantablauf: beide Exit 0, Namespace-/PID-/Netzwerk-/Seccomp-Sandbox vor Zugriff geprüft.
- Unabhängiger tatsächlicher Chromiumreview: drei Kontextfälle grün; eigene Evidenz im benachbarten Reviewordner.
- Endgültiger mobiler Screenshot bei 390px zusätzlich visuell geprüft.

Alle Daten sind synthetisch. Der neue vollständige Browserfall erzeugt echte interne Aufgaben und einen echten Angebotsentwurf im temporären lokalen Server. Kein Versand, keine Zahlung und kein externer Modellaufruf erfolgen. Vier verlorene Antworten (Regel, Scan, Entscheidung, Ausführung) werden mit identischem Originalbody und derselben Vorgangskennung wiederholt.

## Historische Fehler und Zwischenläufe

`logs/` bewahrt sämtliche eigenen Zwischenlogs unverändert. Der erste unabhängige Backendtriggerlauf reproduziert die umgangene bestehende Projektregel; der erste Quellenissue-Test reproduziert eine nicht lesbare Belegkennung im Scanfehler. Beide wurden durch den Backendowner behoben. Der unabhängige Browserreview reproduziert eine späte private Fehlermeldung im neuen Dialog-/Projektkontext; Runtimefix und unveränderte Gegenfälle liegen im benachbarten Reviewordner. Der ältere vollständige Node-Kandidatenlauf552/554 enthält genau diese zwei noch roten Varianten und wird nicht als Abschlussnachweis gezählt.

Frühe Browserstarts enthalten Testhost-/Timingprobleme während der Entwicklung (reguläre Instanzbindung, erwartete LostACK-Folge, noch laufende Historienabfrage); das sind keine zusätzlichen bestätigten Produktfehler. Der erste Owner-Nachlauf traf eine zwischenzeitlich unvollständige Datei, bevor der Syntaxfix abgeschlossen war. Der jeweils ausdrücklich `final` genannte Abschlusslauf ist maßgeblich; ursprüngliche Logs wurden nicht ersetzt.

## Integration

Der JSON-Abschlussmanifest eine Ebene höher enthält genaue Dateigrenzen und SHA-256. Globale Browserdiffs liegen zusätzlich in `shared-browser-hooks.patch`, Basis4c2f0086b4a9979b7cbe9d261fc22a97cd046913. Diese älteren globalen Dateien dürfen aktuelle Source5-/Opening-/Assets-Hooks nicht ersetzen. Es gibt genau einen Dialogzähler; die bestehenden Assets- und neuen Companykontexte verwenden ihn.

Die Browser-CI-Ergänzung ist ausschließlich `SMARTPLAN_BROWSER_WORKFLOW=company-events node tests/e2e.cjs &&` nach dem bisherigen Assistantablauf. Andere Änderungen an `.github/workflows/checks.yml` und die statische Backendallowlist stammen vom Backendowner. Native Dateien und deren Tests gehören einem anderen Owner. Kein Commit durch diesen Scope.
