# Altposten-Browser: überprüfter Integrationsstand

Stand 04.11.2026, isoliertes Arbeitsverzeichnis `/workspace/smartplan-opening-items-20261104`.
[SHA-256-Manifest](../opening-items-browser-2026-11-04.json) und
[Anforderungen/Umsetzung](../../CRM_ERP_ALTPOSTEN_BROWSER_2026-11-04.md).
Dies ist ein Clientnachweis; er behauptet keine Fertigstellung oder Auslieferung des Gesamtziels.

## Endgültige Prüfungen

- `logs/opening-items-node-final-2026-11-04.log`: 644 benannte Tests, 644 bestanden, keine Fehler oder übersprungenen Fälle; echte Ausführung außerhalb des eingeschränkten Node-Testhosts.
- `logs/opening-items-browser-final-2026-11-04.log`: vollständiger echter Chromium-/MFA-/HTTP-Altpostenablauf. Die unveränderten synthetischen Befehle und zwei Screenshots liegen in `artifacts/opening-items-browser-final-2026-11-04/`.
- `logs/opening-items-legacy-bank-final-2026-11-04.log`: vorhandener vollständiger Bankabgleich im echten Browser. Originale synthetische Befehle und Desktop-/390px-Screenshots liegen in `artifacts/opening-items-legacy-bank-final-2026-11-04/`.
- Beide Browserläufe bestätigen vor Anwendungszugriff die Namespace-, PID-, Netzwerk- und Seccomp-Sandbox. Kein Abschaltflag, keine externen Zahlungen, kein Produktivkontakt.

Der neue Browserpfad erfasst echte Originale, erklärt historische Anteile ausdrücklich,
prüft Vorschau/Annahme und wiederholt drei angenommene Aufträge nach verlorener Antwort exakt.
Er deckt Forderung/Verbindlichkeit, drei historische Zahlungsfassungen, EÜR ohne erneute
Vorsteuer, echten Bankabgleich ohne zweite Geldbewegung, Unicode-Kennung,
Originaldownload mit aktuellem Rechteentzug sowie mobile Darstellung ab.
Verzögerte Altposten-/EÜR-Vorschauen und die späte gültige EÜR-Annahme dürfen einen
zwischenzeitlich geöffneten anderen Dialog nicht ersetzen oder schließen.

## Unabhängige Gegenprüfungen

Die unveränderten Manifeste liegen separat:

- `../opening-items-browser-independent-2026-11-04/manifest.json`: 30 unabhängige Fälle, 73 gezielt gemeinsam; elf zuvor reproduzierte EÜR-Kontextvarianten nach Ownerfix grün.
- `../euer-legacy-browser-context-2026-11-04/manifest.json`: 15 unabhängige Bestandsfälle, 88 gezielt gemeinsam; acht echte Bestandsfehler bei `cash` ohne Altpostenfähigkeit waren vorher rot. Tatsächliche Korrektur und Gegenbuchung mit `effect=null` und exakter Pending-Wiederholung nach Editorleeren sind zusätzlich grün.

Die eigenen neuen Vertrags-/Kontextfälle zählen 21. Die vollständigen 644 Tests enthalten
sie und beide unabhängigen Dateien. Gezielt ermittelte Zahlen sind Teilmengen, keine
zusätzlichen Tests außerhalb der Gesamtsumme. Die unabhängigen Node-Tests benutzen einen
kontrollierten DOM-Host; nur die zwei ausdrücklich genannten Chromiumläufe sind Browsernachweise.

## Historische Läufe bleiben erhalten

Die archivierten Dateien sind unveränderte Originalausgaben, einschließlich roter Läufe.
Der erste Vertragslauf hatte zwei zu enge Groß-/Kleinschreibungs-Assertions.
Die ersten Browserläufe korrigierten ausschließlich Testaufbau (HTTP201 statt200,
fehlendes ausdrücklich angelegtes Bankkonto, bereits aktiver EÜR-Reiter,
unerlaubtes zusätzliches Konto-Commandfeld). Die spätere echte Browserprüfung fand
einen veralteten neutralen Pendingzähler nach bereits angenommener EÜR-Bestätigung
bei inzwischen gewechseltem Dialog; der Owner aktualisiert ihn nun nach gültiger
Quittung auch ohne private Ansicht. Der endgültige Browserlauf bestätigt den Fix.

`opening-items-euer-auth-replay-fix-2026-11-04.log` entstand während einer Reviewerdatei-
Ergänzung mit noch nicht gültigem Import; der Dateiaggregatefehler ist kein Produktbefund.
`opening-items-euer-reviewed-current-2026-11-04.log` enthält den anschließend tatsächlich
reproduzierten Rechteentzug während des Quellabrufs. Die unabhängigen Rotbelege und alle
endgültigen grünen Läufe bleiben separat nachvollziehbar. Frühere Snapshotdateien
sind historische Zwischenstände und werden nicht zu endgültigen Quellhashes umgedeutet.

## Integration

`shared-browser-hooks-from-assets.patch` enthält ausschließlich die fünf gemeinsamen
Browserdateien gegenüber den einzeln erneut hashgeprüften Assets-Basisdateien unter
`/workspace/smartplan-assets-integration-20261104`. Die Basisdateiliste wurde vor Beginn
in `work/verification/assets-candidate-baseline.json` festgehalten. Der normale Gitdiff
gegen HEAD enthält zusätzlich geerbte Assetsänderungen und ist dafür nicht geeignet.

Die zwei neuen Produktmodule, drei eigenen neuen Test-/Workflowdateien sowie die neuen
Reviewdateien und Artefakte werden separat übernommen. Die gemeinsame CI-Datei ergänzt
nur die `accounting-open-items`-Workflowzeile; `backend/online/web.py` ergänzt nur die zwei
statischen Modulnamen. Andere Backend-/Native-Änderungen gehören ihren eigenen Ownern.
Vorhandene Company-Events-, Source5-, asynchrone Quittungs- und Dialoggeneration-Hooks
im Integrationsziel bleiben erhalten. Der vorhandene Dialogzähler wird mitverwendet.
