# Jahrespaket-Browser: finaler v1-Clientstand

Stand 04.11.2026, isolierter Baum `/workspace/smartplan-year-review-export-20261104`.
[Abschlussmanifest](../year-package-browser-2026-11-04.json),
[Anforderungen und Umsetzung](../../CRM_ERP_JAHRESPAKET_BROWSER_2026-11-04.md).
Kein Gesamtabschluss, keine Auslieferung oder produktive Außenaktion.
Der finale Backendnachtrag am eingebetteten Offlineprüfer ist berücksichtigt.
Die alte tatsächliche Fixture bleibt unter
`fixtures/backend-v1-before-checker-followup.json` unverändert erhalten.
Die neue tatsächliche Fixture ist SHA-256
`a859f2bbbcfab6f890c2968a05aa2fa839299117ae43b8e15e2d7852c82d36a0`
(719679 Bytes). Alle 659 Nodefälle und der echte Jahrespaket-Browserlauf wurden
dagegen erneut grün ausgeführt; finale Logs heißen
`year-package-checker-followup-node-final-2026-11-04.log` und
`year-package-chromium-checker-followup-2026-11-04.log`. Finale ZIP-/Screenshot-/
HTTPartefakte liegen unter `artifacts/year-package-browser-checker-followup-2026-11-04/`.

## Tatsächliche Prüfungen

- `logs/year-package-full-node-final-2026-11-04.log`: 659 benannte Tests, 659 bestanden, keine Fehler oder übersprungenen Fälle. Enthält 28 neue Ownerfälle und 21 unabhängige Gegenfälle.
- `logs/year-package-chromium-context-fixed-2026-11-04.log`: echter gebundener lokaler Server, MFA, Chromium und tatsächliche ZIP-Datei. Unvollständigkeit, feste Exportbindung, identischer wiederholter Download, eigener Offlineprüfer, beide initialen Antwortreihenfolgen, simulierter Hintergrundzyklus über den echten Browserhook, verzögerte Metadaten/Bytes, beschädigte Bytes, echter globaler Rechteentzug und 390px sind grün. ZIP, Prüfausgabe, HTTPnachweise und Screenshot unter `artifacts/year-package-browser-context-fixed-2026-11-04/`.
- `logs/year-package-legacy-euer-final-2026-11-04.log`: bisheriger vollständiger EÜR-Browserablauf mit Profil, Beleg-/Steuer-/Geldflusszuordnung, tatsächlicher verlorener Antwort, Berichtigung, Anlage/AfA, Gegenbuchung, Monatsabschluss und unverändertem JSON-/CSVexport erneut grün. Artefakte unter `artifacts/year-package-legacy-euer-final-2026-11-04/`.
- Die unabhängige Gegenprüfung liegt getrennt unter `../year-package-browser-independent-2026-11-04/`. Sie enthält 21 eigene Fälle (60 gezielt gemeinsam), sechs unabhängig geprüfte tatsächliche ZIPs und einen eigenen echten Chromiumfall: Nach ZIP200 wird ausschließlich die Finanzfreigabe einer enthaltenen Original-Projektquelle entzogen, während beide globalen Leserechte erhalten bleiben. Der erneute Metadatenabruf liefert403; es bleibt ein neutraler Dialog ohne Download.

Node-Ausführung: `node --test web/office/tests/*.test.mjs`, echte benannte Tests
mit erlaubter Ausführung außerhalb des eingeschränkten Node-Testhosts.
Browser: `node web/office/tests/accounting-year-package-e2e.cjs` beziehungsweise
`node web/office/tests/accounting-euer-e2e.cjs`, mit `NODE_PATH` auf die vorhandene
Playwrightinstallation, `/usr/lib/chromium/chromium`,
`SMARTPLAN_BROWSER_NAMESPACE_SANDBOX=1` und
`SMARTPLAN_BROWSER_TEST_PYTHON=/tmp/smartplan-backend-verified/bin/python`.
Namespace-, PID-, Netzwerk- und Seccomp-Isolation bleiben aktiv. Alle Quellen,
Konten und Benutzer sind synthetisch, alle Anwendungsserver lokal.

## Unveränderte Fehlernachweise

Die ersten zwei roten Nodefälle waren zu kurze synthetische Sitzungstokens.
Der erste Browseraufbau behandelte die tatsächlich als String gelieferte
Benutzerkennung als Objekt. Der zweite Browserlauf zeigte korrekt fehlende
Projektfreigabe des synthetischen Lesers; die tatsächliche Projektzuordnung
wurde vor dem Rechteentzugstest ausdrücklich hergestellt. Diese Ausgaben
bleiben erhalten und werden nicht als Produktfehler bezeichnet.

Der eigene spätere negative Readerfall `year-package-private-boundary-before`
zeigte, dass eine aus Metadaten verschwundene private Originalgrenze trotz
bekannter öffentlicher Lohn-/Reisequelle im ursprünglichen Report noch akzeptiert
wurde. Der Reader weist diese widersprüchliche Antwort nun ab.

Der unabhängige Review reproduzierte drei reale initiale Exportkontextfehler:
alte Erfolgs-/Fehlerantwort nach Hintergrund und Rückkehr sowie A zuerst
antwortend, obwohl B zuletzt ausgewählt war. Die eigene Exportabsichts-Epoche
und der Hintergrundhook invalidieren solche Antworten schon vor dem ersten
Dialog. Die eigenen und unabhängigen endgültigen Nachläufe sind grün. Frühere
Snapshots und `shared-browser-hooks-before-independent.patch` bleiben historische
Zwischenstände; sie sind kein endgültiger Handoff.

## Grenze der nachträglichen Originalauflösung

Der Pflichtanker-Prüfer benötigt den separat authentisiert bestätigten ZIP-Hash.
Eine erfolgreiche Hashprüfung ist kein eigenständiger Vollständigkeitsbeweis
aller ursprünglichen Altbelege und Abhängigkeiten. Der Client benennt diese
Grenze ausdrücklich und gibt den Hash separat aus. Dieser enge Textnachtrag
ändert keine Request-/Kontextbindung. Alte technische Nachweise behaupten
keine nachträglich stärkere intrinsische Garantie.

## Integration

`shared-browser-hooks-from-b0b96024.patch` enthält nur `office.js` und
`accounting-euer.js` gegen den unveränderten Commit
`b0b96024f0a7cf2c7097fb3b77c64032265850a5`. Beide ursprünglichen Dateihashes wurden
gegen den vor Beginn gespeicherten Baselinebeleg geprüft. Anwendung des Patches
auf temporären Originalkopien reproduziert beide finalen Dateien bytegleich;
`shared-patch-application.txt` hält das Ergebnis fest.

Neue Module und Tests werden separat übernommen. Die CI ergänzt lediglich
`node tests/accounting-year-package-e2e.cjs` nach dem bestehenden EÜR-Browserlauf.
Die zwei statischen Modulnamen sind vom Backendowner registriert. Bestehende
Company-Events-, Source5-, Anlagen- und Altpostenhooks im Rootziel bleiben beim
additiven Merge erhalten; `privateContext` und der vorhandene Dialogzähler werden
mitverwendet. Der neue `accountingEuer.invalidateExport()`-Hook gehört in die
tatsächliche Hintergrundbehandlung auch ohne geöffneten Dialog. Er löscht keine
anderen Buchungsentwürfe.
