# Prüfbelege – Browserkatalog, 4. November 2026

- `node.txt`: vollständige Node-Suite, 427/427 grün.
- `chromium.txt`: ein tatsächlicher Chromium-/MFA-/HTTP-Ablauf grün. Namespace-, PID-, Netzwerk- und Seccomp-Sandbox aktiv.
- `local-http.txt`: 2/2 echte Loopback-HTTP-Transportfälle grün.
- `postgresql.txt`: 2/2 echte PostgreSQL-/MFA-/HTTP-Fälle grün, getrennte Runtime-Rolle, aktive Unveränderlichkeitstrigger und Originalbytes nach Wiederöffnung.
- `catalog-imports-receipts.json`: synthetische tatsächlich erhaltene HTTP-Quittungen; Base64-Dateiinhalte durch deren SHA-256 ersetzt. Exakte Originalgleichheit wurde vor dieser Reduktion im Test verglichen.
- Screenshots: tatsächliche Desktop- und 390-Pixel-Vorschau, keine Mockups.
- `../catalog-originals-backend-2026-11-04.txt`: 99 Backendregressionsfälle, 17 davon neu, sowie unabhängige Lifecycleprüfung und negative Kontrollläufe.

Wiederholung aus dem Projektverzeichnis mit den vorhandenen Projektabhängigkeiten:

```sh
node --test web/office/tests/*.test.mjs
PYTHONPATH=backend python -m unittest test_business_catalog_imports test_business_catalog_imports_transport -v
SMARTPLAN_BROWSER_WORKFLOW=catalog-imports node web/office/tests/e2e.cjs
PYTHONPATH=backend python -m unittest online.test_business_catalog_imports_pg -v
```

Der PostgreSQL-Lauf benötigt die bereits vorhandene, streng begrenzte `SMARTPLAN_TEST_DSN` für die disposable Loopback-Testdatenbank und setzt deren öffentliches Schema zurück. Zugangswerte gehören nicht in dieses Repository. Er verändert keine bestehende Restore-Zieldatenbank. Der Browserlauf benötigt einen unterstützten Python-Interpreter und sandboxfähiges Chromium; lokale Interpreter-/Browserpfade können über die bestehenden `SMARTPLAN_BROWSER_*`-Testvariablen gesetzt werden. Keine Sandbox-Abschaltung.
