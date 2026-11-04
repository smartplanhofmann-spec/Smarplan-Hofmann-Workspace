# Unabhängiger Unternehmensereignis-Browserreview · 04.11.2026

Arbeitsbaum: `/workspace/smartplan-company-events-20261104`. Nur neue unabhängige Tests und Nachweise durch diesen Reviewer; Produktkorrektur durch den zuständigen Browserowner. Keine Commits, keine Produktivkontakte.

## Ergebnis und konkreter Befund

**12/12 eigene Gegenfälle sowie 32/32 im gezielten gemeinsamen Node-Lauf sind grün.** Der tatsächliche Chromium-/MFA-/HTTP-Nachlauf besteht alle drei unabhängigen Dialog-/Projektkontextfälle. Die Browser-Sandbox mit Namespace-, PID-, Netzwerk- und Seccomp-Isolation wurde vom bestehenden Testhost vor Anwendungszugriff geprüft.

Der erste unabhängige Lauf reproduzierte **einen Produktfehler in zwei Varianten**: Eine initiale `/plans`-Abfrage wurde zurückgehalten; anschließend wurde ein anderer Dialog geöffnet beziehungsweise das Projekt gewechselt. Eine verspätete erfolgreiche Antwort wurde korrekt ignoriert. Ein verspäteter 409-Fehler mit privatem Alttext/Plan-ID erreichte dagegen die globale `action()`/`showError()`-Anzeige im neuen Kontext. Der rote Nachweis und die damaligen Runtime-/Test-/Fixturehashes liegen in `before-stale-error-fix.txt` und `before-stale-error-hashes.json`.

Der Owner hat die asynchronen Ereigniseinstiege mit demselben Kontextstempel geschützt. Veraltete Fehler werden verworfen; aktuelle Zugriffsfehler neutralisieren private Dialoginhalte. Der Formularpfad verwirft ebenfalls Antworten nach Kontextwechsel. **Die unabhängige Node-Testdatei wurde zwischen rotem und grünem Lauf nicht verändert.**

## Prüffälle

Die zwölf eigenen Nodefälle führen das echte UI-Modul und OfficeApi gegen einen kleinen deterministischen Dialoghost mit tatsächlichen Domainfixtures aus. Dieser Host bildet die relevanten `dialogGeneration`-, `clear()`-, Sitzungs- und Projektwechsel ab; er ist kein realer Browsernachweis.

- Initiale Listen: verspäteter Erfolg und Fehler nach fremdem Dialog, Projektwechsel und Sitzungsersatz.
- Originalquellen: Dokument- beziehungsweise Finanzleserecht während ausstehender Antwort im konkreten Projekt entzogen; Quelltexte, Hashes und IDs verschwinden trotz weiterhin vorhandener globaler Rechte.
- Angenommene Entscheidung: passende Originalquittung darf den eigenen offenen Auftrag auflösen, aber keinen früheren Dialog erneut öffnen.
- Zwei getrennte verlorene Antworten: ausschließlich die gewählte ursprüngliche Aktion mit identischem Body und identischer Nonce quittieren; die andere bleibt offen. Die Pendingübersicht enthält keine Auftragsbodys.
- Fremdquittung: selbst eine formal passende Annahme über einen anderen echten Plan darf den ursprünglichen Auftrag nicht bestätigen; spätere exakte Wiederholung verwendet denselben Originalbody.

Der separate echte Browserhelper ersetzt nur den ausgewählten Workfloweintrag des vorhandenen temporären MFA-/HTTP-Hosts. Er importiert keinen bestehenden fachlichen Flowtest und verändert weder Host noch Produktdatei. Eine zurückgehaltene reale Listenantwort wird nach einem zweiten ausdrücklich geöffneten Ereignisdialog und einem neuen, **nicht abgesendeten** Scaneditor freigegeben. Erfolg und kontrollierter 409-Fehler erhalten den neuen Dialog. Ein dritter Fehlerfall nach echter Projektwahl bleibt ebenfalls ohne private Altanzeige. Es wird kein Ereignisscan, keine Regel, keine Entscheidung oder Fachaktion geschrieben. Fehlermeldung und Verzögerung sind bewusst instrumentiert, Anmeldung, HTTP-Server, Projektwahl und DOM sind tatsächlich ausgeführt.

`browser-after/independent-context-results.json` enthält für alle drei Varianten `privateErrorVisible: false` und `currentContextPreserved: true`. Die drei Screenshots sind dauerhafte Nachweise; `independent-dialog-error.png` wurde zusätzlich visuell geprüft.

Der erste Browserstart traf eine zwischenzeitlich unvollständige Datei während der abgestimmten Ownerkorrektur und kam wegen `Unexpected end of input` nicht bis zum Login. `browser-during-owner-edit.txt` ist deshalb ausdrücklich **kein** Test eines eingefrorenen Produktstands und kein zweiter Produktbefund. Der finale Lauf startete erst nach der Bytefreeze-Meldung des Owners.

## Reproduktion

Im Repository-Hauptverzeichnis:

```sh
node --test web/office/tests/company-events-independent-review.test.mjs web/office/tests/company-events-contract.test.mjs web/office/tests/company-events-access.test.mjs web/office/tests/company-events-session.test.mjs
```

Tatsächlicher lokaler Browsernachlauf (nur synthetischer temporärer Testserver):

```sh
NODE_PATH=/workspace/Smarplan-Hofmann-Workspace/web/office/node_modules SMARTPLAN_BROWSER_NAMESPACE_SANDBOX=1 SMARTPLAN_CHROMIUM_BINARY=/usr/lib/chromium/chromium SMARTPLAN_BROWSER_TEST_PYTHON=/tmp/smartplan-backend-verified/bin/python SMARTPLAN_BROWSER_WORKFLOW=company-events SMARTPLAN_BROWSER_SCREENSHOT_DIR=/tmp/company-events-independent-browser node --require ./web/office/tests/company-events-independent-preload.cjs web/office/tests/e2e.cjs
```

Alle drei neuen JavaScript-Testdateien bestehen `node --check`. Der Review ersetzt weder den vollständigen fachlichen Browserlauf des Owners noch die Backend-/PostgreSQL-/Restore-Abnahme und behauptet keine Fertigstellung der gesamten Software.
