# Browser: Projektstunden und Korrekturverlauf

Basis: `c875ea5a221e5d38533bb7d50a1d96b9c455d22f`, isolierter Worktree `smartplan-project-time-20261104`. Geprüft am 4. November 2026.

Die Browseroberfläche bietet nun bei Zeiteinträgen „Zeiteintrag prüfen“ an. Sie zeigt Projekt, ursprüngliche Stempelereignisse und den separaten Korrekturverlauf. Berechtigte Personen können eine begründete Minutenänderung für einen vom Server bestätigten freigegebenen Arbeitstag erfassen. Die Auswahl stammt aus `approved_work_dates`, nicht aus der Gerätezeitzone. Die Schreibfreigabe wird unmittelbar vor dem Senden erneut gelesen. Bestätigungen müssen zur ausgewählten Zeit, zum Tag, zur Änderung, Begründung und angemeldeten Person passen.

Bei einer verlorenen Antwort werden die bereits gesendeten Werte gesperrt und dieselbe ursprüngliche Anfrage erneut verwendet. Originalereignisse bleiben erhalten. Die Monatskarte zeigt die Nettozeit nach Pausen und Korrekturen. Der Verlauf zeigt auch sekundengenaue vorhandene Korrekturen, obwohl die neue einfache Eingabe ganze Minuten verwendet.

Ergebnis: **5 Node-Tests und 1 tatsächlicher Browserablauf bestanden**, Exit-Code 0. Der letzte maßgebliche Browserlauf steht in `e2e-final-net-total.txt`; `node-tests.txt` enthält die fünf Einzeltests. Syntaxprüfung der beiden Browserquellen und der beiden Testprogramme bestanden. Die Screenshots wurden nach dem letzten Browserlauf erzeugt; die mobile Ansicht mit 390 Pixeln Breite wurde zusätzlich visuell geprüft.

Der Browserablauf verwendet die bestehende lokale Flask-/SQLite-Fixture mit tatsächlicher MFA-Anmeldung und echten HTTP-Aufrufen. Er erfasst im Browser einen zweistündigen Eintrag zum Projekt, gibt den Arbeitstag frei und korrigiert ihn um −30 Minuten. Die erste erfolgreiche Antwort wird absichtlich verworfen; das erneute Senden erhält denselben Body und dieselbe Request-ID. Es entsteht genau eine Korrektur. Originalereignisse bleiben gleich; API-Tageswert und sichtbarer Netto-Monatswert ergeben 1:30 Stunden. Ein tatsächlich angemeldeter Techniker kann seinen Verlauf sehen, erhält keinen Korrekturknopf und wird bei einem direkten Korrekturversuch mit 403 abgewiesen. `time-correction-result.json` enthält die synthetischen Originale und beiden gleichen Annahmeantworten.

Die ersten beiden Startversuche waren durch die Ausführungsumgebung blockiert: zunächst fehlende Loopback-Socketberechtigung (`initial-e2e.txt`), danach fehlende Berechtigung zum Start der Chromium-Namespace-Sandbox (`e2e-network.txt`). Nach automatischer Werkzeugfreigabe lief der Test außerhalb der äußeren Ausführungssandbox; Chromiums eigene Namespace-, PID-, Netzwerk- und Seccomp-Sandbox wurde vor Zugriff auf die Anwendung geprüft. `e2e-browser.txt` und `e2e-final.txt` dokumentieren vorherige erfolgreiche Zwischenstände vor der abschließenden Monatswertprüfung.

Reproduktion aus dem Worktree:

```sh
node --test --test-isolation=none web/office/tests/time-tracking.test.mjs
NODE_PATH=/workspace/Smarplan-Hofmann-Workspace/web/office/node_modules \
SMARTPLAN_BROWSER_WORKFLOW=time-tracking \
SMARTPLAN_BROWSER_TEST_PYTHON=/tmp/smartplan-backend-verified/bin/python \
SMARTPLAN_BROWSER_NAMESPACE_SANDBOX=1 \
SMARTPLAN_CHROMIUM_BINARY=/usr/lib/chromium/chromium \
SMARTPLAN_BROWSER_SCREENSHOT_DIR=/workspace/smartplan-project-time-20261104/docs/evidence/project-time-browser-2026-11-04 \
node web/office/tests/e2e.cjs
```

Der Test erfordert die Berechtigung für lokale Sockets und Chromiums eigene Sandbox. Es wurden keine externen Dienste oder produktiven Kundendaten verwendet. Die mobile Browsergröße ist kein Nachweis einer installierten iPhone- oder Windows-Anwendung. Eine dauerhafte Browser-Offlinespeicherung wurde nicht ergänzt; die mobile Offline-Zeiterfassung wird separat geprüft. Keine Änderung an Lohnberechnungen, Buchungen, Hauptbranch, Deployment oder PostgreSQL.

Abschließender Nachlauf nach der Backend-Korrektur des Datumsfilters für über Mitternacht reichende Schichten: derselbe tatsächliche Browserablauf ist erneut grün, Exit-Code 0 (`e2e-final-overlap.txt`). Quellen vor und nach dem Lauf sind identisch (`overlap-before.json`, `overlap-result.json`). Die neuen synthetischen Ergebnisse und Screenshots liegen separat unter `overlap/`; frühere Ergebnisse bleiben erhalten. Dieser Nachlauf prüft die bestehende Browserstrecke gegen den finalen Backendstand und fügt keinen eigenen Browserfall über Mitternacht hinzu. Das frühere Manifest ist als `manifest-before-overlap.json` erhalten.
